# coding=utf-8
import numpy as np
import pickle as pkl
import scipy.sparse as sp
import sys,math
from scipy.sparse import csr_matrix

#load the node embeddings generated by deepwalk 载入使用deepwalk生成的节点embedding即节点的向量表示
def load_embeddings(filename):
    file = open(filename)
    [n_nodes,dimension] = [int(x) for x in file.readline().split(" ")]#文件第一行写的个数

    embeddings = dict()
    for line in file:
        parts = line.split(" ")
        node_id = int(parts[0])
        node_e = []
        for i in range(dimension):
            node_e.append(float(parts[i+1]))
        embeddings[node_id] = node_e
    if len(embeddings) <n_nodes:
        print(" less embedings than nodes!",len(embeddings),n_nodes)
    embeddings_list = []
    for i in range(n_nodes):
        embeddings_list.append(embeddings[i])
    return embeddings_list

def load_data(dataset_str,filepath):
    """
    Loads input data from gcn/data directory

    ind.dataset_str.***.x => a list recording the observation for each sample（记录每个样本观测值的列表）, x[i] = [(t1,u1),(t2,u2),...,(tn,un)]
    ind.dataset_str.***.y => a list recording the prediction for each sample（记录每个样本预测的列表）, y[i] = dict(u1,u2,...,un)
    ind.dataset_str.graph => a dict in the format {index: [index_of_neighbor_nodes]} as collections.
    ind.dataset_str.emb_32 => a list recording the embeddings of each node记录每个节点embedding的列表
    ind.dataset_str.features => a list recording the features of each ndoe记录每个节点特征的列表

    All objects above must be saved using python pickle module.以上所有对象都必须使用python pickle模块保存。
    :param dataset_str: Dataset name
    :return: All data input files loaded (as well the training/test data).加载的所有数据输入文件（以及训练/测试数据）
    """
    names = ['train.x', 'train.y','val.x', 'val.y','test.x', 'test.y', 'graph','features']
    objects = []

    for i in range(len(names)):
        with open(filepath+"Data/ind.{}.{}".format(dataset_str, names[i]), 'rb') as f:
            if sys.version_info > (3, 0):
                objects.append(pkl.load(f, encoding='latin1'))
            else:
                objects.append(pkl.load(f))

    train_x,train_y,val_x,val_y,test_x,test_y,graph,vertex_features = tuple(objects)
    #ly查看数据集
    print("训练集观测值train_x:", train_x[1])
    print("训练集预测值train_y:", train_y[1])
    #print("val观测值val_x:", val_x)
    #print("val预测值val_y:", val_y)
    #print("test观测值test_val_x:", test_x)
    #print("test预测值test_y:", test_y)
    #print("graph:", graph)
    #print("vertex_features:", vertex_features)

    #get adjacency matrix得到邻接矩阵
    edges = dict()
    users = set()
    for src in graph:
        dsts = graph[src]
        users.add(src)
        for j in range(len(dsts)):
            dst = dsts[j]
            if src != dst:
                edges[(src,dst)] = 1
            users.add(dst)
    print("total number of users:",len(users))
    print("total number of edges:",len(edges))

    row = []
    col = []
    data = []
    for e in edges.keys():
        (src,dst) = e
        weight = edges[e]
        row.append(src)
        col.append(dst)
        data.append(weight)
    adj = csr_matrix((data,(row,col)),shape=(len(users),len(users)))#CSR方法采取按行压缩的办法, 将原始的矩阵用三个数组进行表示

    #get influence representations
    #得到影响力表示
    node_vec = load_embeddings(filepath + "Data/" + dataset_str + '.emb_32')
    n_nodes = adj.shape[0]
    inputs_features = []
    for i in range(n_nodes):
        inputs_features.append([])
    print("dimension of node embeddings:", len(node_vec), len(node_vec[0]))
    print("dimension of vertex features:", len(vertex_features), len(vertex_features[0]))
    for i in range(n_nodes):
        inputs_features[i] = inputs_features[i] + node_vec[i]
    #print(inputs_features[1], node_vec[1])
    for i in range(n_nodes):
        inputs_features[i] = inputs_features[i] + vertex_features[i]# 其实是将embedding和vertex_feature两者并起来得到该顶点的input_feature
    #print(inputs_features[1],vertex_features[1])
    print("total number of influence dimensions:", len(inputs_features[0]))

    return adj, train_x,train_y,val_x,val_y,test_x,test_y,inputs_features


def sparse_to_tuple(sparse_mx): # 将矩阵转换成tuple格式并返回
    """Convert sparse matrix to tuple representation."""
    def to_tuple(mx):
        if not sp.isspmatrix_coo(mx):
            mx = mx.tocoo()
        coords = np.vstack((mx.row, mx.col)).transpose()#vstack()返回结果为numpy的数组；numpy.transpose()是对矩阵按照所需的要求的转置
        values = mx.data
        shape = mx.shape
        return coords, values, shape

    if isinstance(sparse_mx, list):
        for i in range(len(sparse_mx)):
            sparse_mx[i] = to_tuple(sparse_mx[i])
    else:
        sparse_mx = to_tuple(sparse_mx)

    return sparse_mx


def normalize_adj(adj):# 图归一化并返回
    """ normalize adjacency matrix."""
    adj = sp.coo_matrix(adj)
    rowsum = np.array(adj.sum(1))
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = sp.diags(d_inv_sqrt)
    return adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt).tocoo()


def preprocess_adj(adj,normalize):#处理得到GCN中的归一化矩阵并返回
    """Preprocessing of adjacency matrix for simple GCN model and conversion to tuple representation."""
    if normalize:
            adj_normalized = normalize_adj(adj)
    else:
            adj_normalized = sp.coo_matrix(adj).tocoo()
    return sparse_to_tuple(adj_normalized)


def construct_feed_dict(support, placeholders):# 构建输入字典并返回
    """Construct feed dictionary."""
    feed_dict = dict()
    (indices,_,_) = support
    indices_inverse = np.zeros(shape=[len(indices),2],dtype=np.int64)
    for i in range(len(indices)):
        [x,y] = indices[i]
        indices_inverse[i][0] = y
        indices_inverse[i][1] = x
    feed_dict.update({placeholders['support_indices']: indices_inverse})

    return feed_dict

