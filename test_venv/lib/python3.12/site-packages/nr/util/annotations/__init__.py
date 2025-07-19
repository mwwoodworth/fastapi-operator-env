
""" A set of helper functions that make it easy to attach arbitrary data to functions or classes. """

from __future__ import annotations

import types
import typing as t

import typing_extensions as te

from nr.util.generic import T

_ANNOTATION_MEMBER_NAME = '__nr_util_annotations__'

Annotateable: te.TypeAlias = 'types.FunctionType | type | t.Any'


def add_annotation(obj: Annotateable, annotation_base_type: t.Type[T], annotation: T, front: bool = False) -> None:
  """
  Registers an annotation in the given object, grouped under the specified base type. All annotations added to
  the object can be retrieved with #get_annotations() or #get_annotation(). If *front* is enabled, the annotation
  will be inserted at the front of the group instead of appended to the back.
  """

  if not hasattr(obj, _ANNOTATION_MEMBER_NAME):
    setattr(obj, _ANNOTATION_MEMBER_NAME, {})

  annotations: dict[type, list] = getattr(obj, _ANNOTATION_MEMBER_NAME)
  items = annotations.setdefault(annotation_base_type, [])
  items.insert(0, annotation) if front else items.append(annotation)


def get_annotations(obj: Annotateable, annotation_base_type: t.Type[T]) -> list[T]:
  """
  Returns all annotations registered on the given object in the group of the base type.
  """

  annotations: dict[type, list] = getattr(obj, _ANNOTATION_MEMBER_NAME, {})
  return list(annotations.get(annotation_base_type, []))


def get_annotation(obj: Annotateable, annotation_base_type: t.Type[T]) -> T | None:
  """
  Returns the first annotation registered to the given object in the group of the base type,
  or `None` if no annotations are registered for the given base type.
  """

  annotations = get_annotations(obj, annotation_base_type)
  return annotations[0] if annotations else None
