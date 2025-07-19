
import typing as t

from nr.util.digraph import DiGraph, E, K, N


def remove_with_predecessors(graph: DiGraph[K, N, E], nodes: t.Iterable[K]) -> None:
  """ Remove the given nodes from the graph, and their predecessors if they are not inputs to nodes that are kept on
  the graph. """

  untangle: set[K] = set()

  for node_id in nodes:
    untangle.update(graph.predecessors(node_id))
    del graph.nodes[node_id]

  while untangle:
    next_stage: set[K] = set()
    for node_id in untangle:
      if node_id not in graph.nodes: continue
      if not graph.successors(node_id):
        next_stage.update(graph.predecessors(node_id))
        del graph.nodes[node_id]
    untangle = next_stage
