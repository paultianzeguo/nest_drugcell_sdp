import time
import torch
import torch.optim as optim
import torch.utils.data as du
from torch.autograd import Variable
from sklearn.model_selection import train_test_split

import util
from training_data_wrapper import *
from drugcell_nn import *


class NNTrainer():

	def __init__(self, opt):

		self.data_wrapper = TrainingDataWrapper(opt)

		self.model = DrugCellNN(self.data_wrapper)
		self.model.cuda(self.data_wrapper.cuda)


	def train_model(self):

		epoch_start_time = time.time()
		best_model = 0
		max_corr = 0

		train_features, train_labels = self.data_wrapper.train_data
		train_feature, val_feature, train_label, val_label = train_test_split(train_features, train_labels, test_size = 0.1, shuffle = False)

		term_mask_map = util.create_term_mask(self.model.term_direct_gene_map, self.model.gene_dim, self.data_wrapper.cuda)
		for name, param in self.model.named_parameters():
			term_name = name.split('_')[0]
			if '_direct_gene_layer.weight' in name:
				param.data = torch.mul(param.data, term_mask_map[term_name]) * 0.1
			else:
				param.data = param.data * 0.1

		train_label_gpu = Variable(train_label.cuda(self.data_wrapper.cuda))
		val_label_gpu = Variable(val_label.cuda(self.data_wrapper.cuda))
		train_loader = du.DataLoader(du.TensorDataset(train_feature, train_label), batch_size = self.data_wrapper.batchsize, shuffle = False)
		val_loader = du.DataLoader(du.TensorDataset(val_feature, val_label), batch_size = self.data_wrapper.batchsize, shuffle = False)

		optimizer = torch.optim.Adam(model.parameters(), lr = self.data_wrapper.learning_rate, betas = (0.9, 0.99), eps = 1e-05)
		optimizer.zero_grad()

		for epoch in range(self.data_wrapper.epochs):
			# Train
			self.model.train()
			train_predict = torch.zeros(0, 0).cuda(self.data_wrapper.cuda)

			for i, (inputdata, labels) in enumerate(train_loader):
				# Convert torch tensor to Variable
				features = util.build_input_vector(inputdata, self.data_wrapper.cell_features, self.data_wrapper.drug_features)
				cuda_features = Variable(features.cuda(self.data_wrapper.cuda))
				cuda_labels = Variable(labels.cuda(self.data_wrapper.cuda))

				# Forward + Backward + Optimize
				optimizer.zero_grad()  # zero the gradient buffer

				# Here term_NN_out_map is a dictionary
				aux_out_map, _ = self.model(cuda_features)

				if train_predict.size()[0] == 0:
					train_predict = aux_out_map['final'].data
				else:
					train_predict = torch.cat([train_predict, aux_out_map['final'].data], dim = 0)

				total_loss = 0
				for name, output in aux_out_map.items():
					loss = nn.MSELoss()
					total_loss += loss(output, cuda_labels)
				total_loss.backward()

				for name, param in self.model.named_parameters():
					if '_direct_gene_layer.weight' not in name:
						continue
					term_name = name.split('_')[0]
					param.grad.data = torch.mul(param.grad.data, term_mask_map[term_name])

				optimizer.step()

			train_corr = util.pearson_corr(train_predict, train_label_gpu)

			self.model.eval()

			val_predict = torch.zeros(0, 0).cuda(self.data_wrapper.cuda)

			for i, (inputdata, labels) in enumerate(val_loader):
				# Convert torch tensor to Variable
				features = util.build_input_vector(inputdata, self.data_wrapper.cell_features, self.data_wrapper.drug_features)
				cuda_features = Variable(features.cuda(self.data_wrapper.cuda))
				aux_out_map, _ = self.model(cuda_features)

				if val_predict.size()[0] == 0:
					val_predict = aux_out_map['final'].data
				else:
					val_predict = torch.cat([val_predict, aux_out_map['final'].data], dim = 0)

			val_corr = util.pearson_corr(val_predict, val_label_gpu)

			if val_corr >= max_corr:
				max_corr = val_corr

			epoch_end_time = time.time()
			print("epoch %d\ttrain_corr %.4f\tval_corr %.4f\ttotal_loss %.4f\telapsed_time %s" % (epoch, train_corr, val_corr, total_loss, epoch_end_time - epoch_start_time))
			epoch_start_time = epoch_end_time

		torch.save(self.model, self.data_wrapper.modeldir + '/model_final.pt')

		return max_corr
