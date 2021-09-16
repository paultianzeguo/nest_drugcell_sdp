
import argparse
import sys
import os
import numpy as np
import torch
import torch.utils.data as du
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F

import util


def predict_drugcell(predict_data, gene_dim, drug_dim, model_file, hidden_folder, batch_size, result_file, cell_features, drug_features):

	feature_dim = gene_dim + drug_dim

	model = torch.load(model_file, map_location='cuda:%d' % CUDA_ID)

	predict_feature, predict_label = predict_data

	predict_label_gpu = predict_label.cuda(CUDA_ID)

	model.cuda(CUDA_ID)
	model.eval()

	test_loader = du.DataLoader(du.TensorDataset(predict_feature,predict_label), batch_size=batch_size, shuffle=False)

	#Test
	test_predict = torch.zeros(0,0).cuda(CUDA_ID)
	term_hidden_map = {}

	saved_grads = {}
	def save_grad(term):
		def savegrad_hook(grad):
			saved_grads[term] = grad
		return savegrad_hook

	for i, (inputdata, labels) in enumerate(test_loader):
		# Convert torch tensor to Variable
		features = util.build_input_vector(inputdata, cell_features, drug_features)

		cuda_features = Variable(features.cuda(CUDA_ID), requires_grad=True)

		# make prediction for test data
		aux_out_map, term_hidden_map = model(cuda_features)

		if test_predict.size()[0] == 0:
			test_predict = aux_out_map['final'].data
		else:
			test_predict = torch.cat([test_predict, aux_out_map['final'].data], dim=0)

		for term, hidden_map in term_hidden_map.items():
			hidden_file = hidden_folder+'/'+term+'.hidden'
			with open(hidden_file, 'ab') as f:
				np.savetxt(f, hidden_map.data.cpu().numpy(), '%.4e')

		for term, _ in term_hidden_map.items():
			term_hidden_map[term].register_hook(save_grad(term))

		## Do backprop
		aux_out_map['final'].backward(torch.ones_like(aux_out_map['final']))

		# Save Feature Grads
		feature_grad = torch.zeros(0,0).cuda(CUDA_ID)
		feature_grad = cuda_features.grad.data
		with open(result_file + '_feature_grad.txt', 'ab') as f:
			np.savetxt(f, feature_grad.cpu().numpy(), '%.4e', delimiter='\t')

		# Save Hidden Grads
		for term, hidden_grad in saved_grads.items():
			hidden_file = hidden_folder + '/' + term + '.hidden_grad'
			with open(hidden_file, 'ab') as f:
				np.savetxt(f, hidden_grad.data.cpu().numpy(), '%.4e', delimiter='\t')

	test_corr = util.pearson_corr(test_predict, predict_label_gpu)
	print("Test pearson corr\t%s\t%.6f" % (model.root, test_corr))

	np.savetxt(result_file + '.txt', test_predict.cpu().numpy(),'%.4e')


parser = argparse.ArgumentParser(description='Predict DrugCell')
parser.add_argument('-predict', help='Dataset to be predicted', type=str)
parser.add_argument('-batchsize', help='Batchsize', type=int, default=1000)
parser.add_argument('-gene2id', help='Gene to ID mapping file', type=str)
parser.add_argument('-drug2id', help='Drug to ID mapping file', type=str)
parser.add_argument('-cell2id', help='Cell to ID mapping file', type=str)
parser.add_argument('-load', help='Model file', type=str)
parser.add_argument('-hidden', help='Hidden output folder', type=str, default='hidden/')
parser.add_argument('-result', help='Result file prefix', type=str, default='result/predict')
parser.add_argument('-cuda', help='Specify GPU', type=int, default=0)
parser.add_argument('-genotype', help='Mutation information for cell lines', type=str)
parser.add_argument('-fingerprint', help='Morgan fingerprint representation for drugs', type=str)
parser.add_argument('-zscore_method', help='zscore method (zscore/robustz)', type=str)

opt = parser.parse_args()
torch.set_printoptions(precision=5)

predict_data, cell2id_mapping, drug2id_mapping = util.prepare_predict_data(opt.predict, opt.cell2id, opt.drug2id, opt.zscore_method)
gene2id_mapping = util.load_mapping(opt.gene2id, "genes")

# load cell/drug features
cell_features = np.genfromtxt(opt.genotype, delimiter=',')
drug_features = np.genfromtxt(opt.fingerprint, delimiter=',')

num_cells = len(cell2id_mapping)
num_drugs = len(drug2id_mapping)
num_genes = len(gene2id_mapping)
drug_dim = len(drug_features[0,:])

CUDA_ID = opt.cuda

predict_drugcell(predict_data, num_genes, drug_dim, opt.load, opt.hidden, opt.batchsize, opt.result, cell_features, drug_features)
