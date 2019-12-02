# coding=utf-8
# Copyright 2019 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collections of partitioning functions."""

import time
import metis
import scipy.sparse as sp
import tensorflow as tf
import numpy as np
import pdb

def partition_graph_by_label(label):
  groups = []
  # import pdb; pdb.set_trace()
  for node in range(label.shape[0]):
    node_label = np.argwhere(label[node,:]).squeeze(-1)
    node_label = node_label[0] if len(node_label) else -1
    groups.append(node_label)
  return groups

def partition_graph(adj, idx_nodes, num_clusters, y=None):
  """
  partition a graph by METIS.
  idx_nodes: visible_data (train_data)
  y: add lable constraint
  """

  start_time = time.time()
  num_nodes = len(idx_nodes)
  num_all_nodes = adj.shape[0]
  neighbor_intervals = []
  neighbors = []
  edge_cnt = 0
  neighbor_intervals.append(0)
  train_adj_lil = adj[idx_nodes, :][:, idx_nodes].tolil()
  train_ord_map = dict()
  train_adj_lists = [[] for _ in range(num_nodes)]
  for i in range(num_nodes):
    rows = train_adj_lil[i].rows[0] # columns of each row
    # self-edge needs to be removed for valid format of METIS
    if i in rows:
      rows.remove(i)  # remove self edges
    train_adj_lists[i] = rows
    neighbors += rows
    edge_cnt += len(rows)
    neighbor_intervals.append(edge_cnt)
    train_ord_map[idx_nodes[i]] = i

  if y is not None:
    groups = partition_graph_by_label(y) 
    num_clusters = y.shape[1]  # set cluster number to the size of label
    print(f'num_clusters: {num_clusters}, partition graph by label')
  else:
    if num_clusters > 1:
      _, groups = metis.part_graph(train_adj_lists, num_clusters, seed=1)
    else:
      groups = [0] * num_nodes  # TODO,cluster based on labels

  part_row = []
  part_col = []
  part_data = []
  parts = [[] for _ in range(num_clusters)]
  for nd_idx in range(num_nodes):
    gp_idx = groups[nd_idx]
    if gp_idx < 0:
      continue
    nd_orig_idx = idx_nodes[nd_idx]
    parts[gp_idx].append(nd_orig_idx)
    for nb_orig_idx in adj[nd_orig_idx].indices: # neibourhood index of node nd_orig_idx
      nb_idx = train_ord_map[nb_orig_idx]
      # if (y is not None and any(y[nd_idx]==y[nb_idx])) or (y is None and groups[nb_idx]==gp_idx):
      if y is None or any(y[nd_idx]==y[nb_idx]) is False:
      #   continue
      # elif groups[nb_idx] != gp_idx:
      #   continue
        part_data.append(1)
        part_row.append(nd_orig_idx)
        part_col.append(nb_orig_idx)
  part_data.append(0)
  part_row.append(num_all_nodes - 1)
  part_col.append(num_all_nodes - 1) # guarantee boundary of coo_matrix
  # pdb.set_trace()
  part_adj = sp.coo_matrix((part_data, (part_row, part_col))).tocsr()

  tf.logging.info('Partitioning done. %f seconds.', time.time() - start_time)
  return part_adj, parts
