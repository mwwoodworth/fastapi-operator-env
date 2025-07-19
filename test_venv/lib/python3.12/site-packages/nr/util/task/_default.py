
"""
Provides the #DefaultTaskManager which operates locally to run tasks in a pool of threads.
"""

import dataclasses
import logging
import queue
import sys
import threading
import time
import typing as t
import uuid
import weakref

from nr.util.atomic import AtomicCounter
from nr.util.generic import T

from . import _api as api

logger = logging.getLogger(__name__)


class TaskCallbacks(api.TaskCallbacks):

  class _Entry(t.NamedTuple):
    condition: api.TaskCallbackCondition
    callback: api.TaskCallback
    once: bool
    group: t.Optional[str]

  def __init__(self, task: 'Task') -> None:
    self._task = weakref.ref(task)
    self._lock = task._lock
    self._callbacks: t.Dict[str, TaskCallbacks._Entry] = {}

  def __repr__(self) -> str:
    task = self._task()
    assert task is not None
    return f'<_TaskCallbacks task={task.name!r} size={len(self._callbacks)}>'

  def add(
    self,
    condition: api.TaskCallbackCondition,
    callback: api.TaskCallback,
    once: bool = True,
    group: t.Optional[str] = None,
  ) -> None:
    """
    Add a callback to the collection. If the *group* is specified, it can be used to remove
    the callbacks from the task wtih #remove_group(). The #condition determines when the *callback*
    will be invoked. If it returns `True` at the time when #add() is used, the *callback* is invoked
    immediately and will not be added to the collection.

    # Arguments
    condition: The condition on which to invoke them *callback*.
    callback: The callback to invoke when the task status is updated and the *condition* matches.
    once: If set to `True`, the callback will be invoked only once and removed from the task after.
    group: A string that identifies the group that the callback belongs to.
    """

    assert callable(callback)
    task = self._task()
    assert task is not None

    with self._lock:
      run_now = condition(task)
      if not run_now:
        self._callbacks[str(uuid.uuid4())] = TaskCallbacks._Entry(condition, callback, once, group)

    if run_now:
      callback(task)

  def remove(self, *, group: str) -> None:
    """
    Remove all callbacks from the collection that belong to the specified *group*.
    """

    with self._lock:
      self._callbacks = {k: e for k, e in self._callbacks.items() if e.group != group}

  def _invoke(self) -> None:
    """
    Internal. Invokes all callbacks based on their condition.
    """

    task = self._task()
    assert task is not None

    with self._lock:
      callbacks = self._callbacks.copy()

    remove: t.Set[str] = set()
    for key, entry in callbacks.items():
      try:
        do_run = entry.condition(task)
      except:
        task.logger.exception(f'Unhandled exception in callback condition of task "%s": %s', task.name, entry.condition)
        continue
      if not do_run:
        continue
      if entry.once:
        remove.add(key)
      try:
        entry.callback(task)
      except:
        task.logger.exception(f'Unhandled exception in callback of task "%s": %s', task.name, entry.callback)

    with self._lock:
      self._callbacks = {k: e for k, e in self._callbacks.items() if k not in remove}


class Task(api.Task[T]):

  def __init__(self, runnable: api.Runnable[T], name: str) -> None:
    self._lock = threading.RLock()
    self._cond = threading.Condition(self._lock)
    self._runnable = runnable
    self._id = type(self).__module__ + '.' + type(self).__name__ + '.' + str(uuid.uuid4())
    self._worker_id: t.Optional[str] = None
    self._name = name
    self._logger = self._create_logger()
    self._callbacks = TaskCallbacks(self)
    self._cancelled = threading.Event()
    self._status = api.TaskStatus.PENDING
    self._error: t.Optional[api.ExcInfoType] = None
    self._error_consumed: bool = False
    self._result: t.Optional[T] = None

  def _create_logger(self) -> logging.Logger:
    fqn = type(self).__module__ + '.' + type(self).__name__
    return logging.getLogger(f'{fqn}[{self.name}]')

  def _update(self, status: api.TaskStatus, result: t.Optional[T] = None, error: t.Optional[api.ExcInfoType] = None) -> None:
    """
    Update the status of the task. This should be used only by the executor engine where the task
    is queued. A status change will immediately invoke the registered #callbacks. Some status
    transitions are not allowed (ex. from #api.TaskStatus.SUCCEEDED to #api.TaskStatus.RUNNING). In this
    case, a #RuntimeError will be raised. Similarly, if the *status* is #api.TaskStatus.FAILED but
    no *error* is given, a #RuntimeError will be raised as well.
    """

    if status == api.TaskStatus.FAILED and error is None:
      raise RuntimeError(f'missing error information for setting task status to FAILED')

    if result is not None and status != api.TaskStatus.SUCCEEDED:
      raise RuntimeError(f'cannot set result with status {status.name}')

    with self._cond:
      if (self._status.completed and self._status != status) or (self._status == api.TaskStatus.RUNNING and status.idle):
        raise RuntimeError(f'changing the task status from {self._status.name} to {status.name} is not allowed')
      invoke_callbacks = status != self._status
      self._status = status
      self._error = error
      self._result = result
      self._cond.notify_all()

    if invoke_callbacks:
      self.callbacks._invoke()

  @property
  def runnable(self) -> api.Runnable: return self._runnable

  @property
  def id(self) -> str: return self._id

  @property
  def worker_id(self) -> t.Optional[str]: return self._worker_id

  @property
  def name(self) -> str: return self._name

  @property
  def logger(self) -> logging.Logger: return self._logger

  @property
  def callbacks(self) -> TaskCallbacks: return self._callbacks

  @property
  def status(self) -> api.TaskStatus:
    """
    Returns the current status of the task.
    """

    with self._lock:
      return self._status

  @property
  def error(self) -> t.Optional[api.ExcInfoType]:
    """
    Returns the exception that occurred while executing the task. This is only set if
    the #status is #api.TaskStatus.FAILED.
    """

    with self._lock:
      return self._error

  @property
  def error_consumed(self) -> bool:
    """
    Returns #True if the error in the task is marked as consumed.
    """

    with self._lock:
      return self._error_consumed

  @property
  def result(self) -> t.Optional[T]:
    with self._lock:
      if self._status == api.TaskStatus.IGNORED:
        return None
      elif self._status == api.TaskStatus.FAILED:
        assert self._error is not None, 'Task status is FAILED but no error is set'
        raise self._error[1]
      elif self._status in (api.TaskStatus.SUCCEEDED, api.TaskStatus.CANCELLED):
        return self._result
      else:
        raise RuntimeError(f'Task has status {self._status.name}')

  def consume_error(self, origin: t.Optional[str] = None) -> None:
    """
    Mark the error in the task as consumed. This can be called from a callback, but can only be
    called if the #status is #api.TaskStatus.FAILED.
    """

    with self._lock:
      if self._status != api.TaskStatus.FAILED:
        raise RuntimeError(f'task status must be FAILED to call Task.consume_error() but is {self._status.name}')
      self._error_consumed = True

  def cancel(self) -> None:
    """
    Set the cancelled flag on the task. After calling this method, #cancelled() will return `True`
    and any thread that is currently using #sleep() will be immediately woken up (rather than
    waiting for the timeout to kick in).
    """

    self._cancelled.set()

  def cancelled(self) -> bool:
    """
    Returns `True` if the task has been cancelled (with the #cancel() methdo). The task subclass
    should use this to check if execution should continue or not.
    """

    if self._cancelled is None:
      raise RuntimeError('Task is not connected to a worker')
    return self._cancelled.is_set()

  def sleep(self, duration: float) -> bool:
    """
    Sleep for *sec* seconds, or until the task is cancelled with the #cancel() method. This should
    be used instead of #time.sleep() inside the task's #run() implementation to ensure quick
    task termination.

    Returns `True` if the task has been cancelled (saving a subsequent call to #cancelled()).
    """

    if self._cancelled is None:
      raise RuntimeError('Task is not connected to a worker')
    return not self._cancelled.wait(duration)

  def join(self, timeout: t.Optional[float] = None) -> bool:
    with self._cond:
      return self._cond.wait_for(lambda: self._status.completed, timeout)


class TaskPriorityQueue:

  def __init__(self) -> None:
    self._q: 'queue.PriorityQueue[t.Tuple[float, t.Optional[Task]]]' = queue.PriorityQueue()
    self._max_time: t.Optional[float] = None
    self._cond = threading.Condition(threading.Lock())
    self._total = AtomicCounter()
    self._current = AtomicCounter()

  def total(self) -> int: return self._total.get()

  def pending(self) -> int: return max(0, self._total.get() - self._current.get())

  def current(self) -> int: return self._current.get()

  def max_time(self) -> t.Optional[float]:
    with self._cond:
      return self._max_time

  def task_done(self) -> None:
    self._q.task_done()
    self._current.dec()
    self._total.dec()

  def put(self, at: float, task: Task) -> None:
    assert isinstance(at, float)
    assert isinstance(task, Task)
    with self._cond:
      self._q.put((at, task))
      self._total.inc()
      self._max_time = at if self._max_time is None else max (at, self._max_time)
      self._cond.notify()

  def put_stop(self, at: float) -> None:
    with self._cond:
      self._q.put((at, None))
      self._cond.notify_all()

  def get(self) -> t.Optional[Task]:
    while True:
      at, task = self._q.get()
      if task is None:
        self._q.task_done()
        return None

      t = time.time()
      if at <= t or task.cancelled():
        self._current.inc()
        return task

      with self._cond:
        self._q.task_done()
        self._q.put((at, task))
        self._cond.wait(timeout=at - t)

  def join_total(self) -> None:
    self._total.join()

  def join_current(self) -> None:
    self._current.join()


@dataclasses.dataclass
class Worker:
  """
  The worker thread accepts tasks from a queue and executes them. Receiving #None from the queue
  indicates to the worker that its should stop.
  """

  #: The name of the worker is used as the thread name.
  name: str

  #: The queue to retrieve new tasks from.
  queue: TaskPriorityQueue

  def __post_init__(self) -> None:
    self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
    self._lock = threading.Lock()
    self._current_task: t.Optional[Task] = None

  def __repr__(self) -> str:
    return f'Worker(name={self.name!r})'

  def _run(self) -> None:
    logger.info('Start worker %s', self.name)
    try:
      self._mainloop()
    except:
      logging.exception('Unhandled exception in worker "%s"', self.name)
    logger.info('Stopped worker %s', self.name)

  def _mainloop(self) -> None:
    while True:
      task = self.queue.get()
      if task is None:
        break
      if task.cancelled():
        task._update(api.TaskStatus.IGNORED)
        self.queue.task_done()
        continue
      with self._lock:
        self._current_task = task
      try:
        self._run_task(task)
      finally:
        with self._lock:
          self._current_task = None
        self.queue.task_done()

  def _run_task(self, task: Task) -> None:
    logger.info('Running task "%s"', task.name)

    try:
      task._worker_id = self.name
      task._update(api.TaskStatus.RUNNING)
      result = task.runnable.run(task)
    except:
      task._update(api.TaskStatus.FAILED, t.cast(api.ExcInfoType, sys.exc_info()))
      if not task._error_consumed:
        logger.exception('Unhandled exception in task "%s"', task.name)
    else:
      task._update(api.TaskStatus.CANCELLED if task.cancelled() else api.TaskStatus.SUCCEEDED, result)
    finally:
      logger.info('Finished task "%s"', task.name)

  def get_current_task(self) -> t.Optional[Task]:
    with self._lock:
      return self._current_task

  def start(self) -> None:
    self._thread.start()


@dataclasses.dataclass  # type: ignore
class DefaultExecutor(api.Executor):

  _CALLBACK_GROUP = '_TaskManager'

  #: The name of the task manager. This is used as the prefix for created #Worker names.
  name: str

  #: The maximum number of workers to spawn. Defaults to 8,
  max_workers: int = 8

  def __post_init__(self) -> None:
    #: A list of the workers assigned to the pool that is bounded by #max_size.
    self._pool_workers: t.List[Worker] = []

    #: The queue that is used to send tasks to the workers.
    self._queue = TaskPriorityQueue()

    #: A counter for all tasks submitted to the task manager that have not yet completed.
    self._all_tasks = AtomicCounter()

    #: A counter for all currently active tasks.
    self._active_tasks = AtomicCounter()

    self._lock = threading.Lock()
    self._shutdown = False

  def execute(
    self,
    runnable: api.Runnable[T],
    name: t.Optional[str] = None,
    at: t.Optional[float] = None,
  ) -> Task[T]:
    """
    Queue a task for execution in the worker pool. If there is a free slot in the pool and all
    existing workers are busy, a new worker will be spawned immediately.
    """

    assert isinstance(runnable, api.Runnable), f'expected instance of Runnable, got {type(runnable).__name__} instead'
    if self._shutdown:
      raise RuntimeError('task manager is shut down')

    task = Task(runnable, name or repr(runnable))
    task._update(api.TaskStatus.QUEUED)
    self._queue.put(at or time.time(), task)
    size = self._all_tasks.get()
    if size >= len(self._pool_workers) and size < self.max_workers:
      self._spawn_pool_worker()
    return task

  def _spawn_pool_worker(self) -> None:
    worker = Worker(f'{self.name}-Worker-{len(self._pool_workers)}', self._queue)
    worker.start()
    self._pool_workers.append(worker)

  def get_worker_count(self) -> int:
    return len(self._pool_workers)

  def get_idle_worker_count(self) -> int:
    return len(self._pool_workers) - self._queue.current()

  def shutdown(self, cancel_running_tasks: bool = True, block: bool = True) -> None:
    if self._shutdown:
      raise RuntimeError('shut down already initiated or completed')
    self._shutdown = True

    logger.info('Sending shutdown signal to workers')

    for worker in self._pool_workers:
      if cancel_running_tasks:
        task = worker.get_current_task()
        if task is not None:
          task.cancel()
      # Use the current time to jump in front of pending tasks.
      self._queue.put_stop(0)

    if block:
      self._queue.join_current()

  def join(self) -> None:
    self._queue.join_total()
