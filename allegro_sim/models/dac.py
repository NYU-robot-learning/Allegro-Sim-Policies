import torch
import torch.nn as nn

from allegro_sim.utils import *
from .utils import *

# Deep Actor Critic models

class Identity(nn.Module):
	'''
	Author: Janne Spijkervet
	url: https://github.com/Spijkervet/SimCLR
	'''
	def __init__(self):
		super(Identity, self).__init__()

	def forward(self, x):
		return x


class Actor(nn.Module):
	def __init__(self, repr_dim, action_shape, feature_dim, hidden_dim, offset_mask):
		super().__init__()


		self.policy = nn.Sequential(nn.Linear(repr_dim + action_shape[0]*100, hidden_dim), # TODO: Why multiply with 100??
									nn.ReLU(inplace=True),
									nn.Linear(hidden_dim, hidden_dim),
									nn.ReLU(inplace=True),
									nn.Linear(hidden_dim, action_shape[0]))
		self.offset_mask = torch.tensor(offset_mask).float().to(torch.device('cuda')) # NOTE: This is used to set the exploration

		self.apply(weight_init)

		# Orthogonal initialization
		# for m in self.policy.modules():
		# 	if isinstance(m, (nn.Conv2d, nn.Linear)):
		# 		print('initing ortho - m: {}'.format(m))
		# 		nn.init.orthogonal_(m.weight)

	def forward(self, obs, action, std):

		action = action.repeat(1, 100) # Action shape (1, A) -> (1, 100*A)
		print('action.shape in Actor forward: {}'.format(action.shape))
		h = torch.cat((obs, action), dim=1) # h shape: (1, 100*A + Repr_Dim)
		mu = self.policy(h) 
		mu = torch.tanh(mu) * self.offset_mask

		std = torch.ones_like(mu) * std * self.offset_mask

		dist = TruncatedNormal(mu, std)
		return dist


class Critic(nn.Module):
	def __init__(self, repr_dim, action_shape, feature_dim, hidden_dim):
		super().__init__()

		# NOTE: This was not in the original fish paper!!!
		self.trunk = nn.Sequential(nn.Linear(repr_dim, feature_dim),
                                   nn.LayerNorm(feature_dim), nn.Tanh())

		self.Q1 = nn.Sequential(
			nn.Linear(feature_dim + action_shape[0], hidden_dim),
			nn.ReLU(inplace=True), nn.Linear(hidden_dim, hidden_dim),
			nn.ReLU(inplace=True), nn.Linear(hidden_dim, 1))

		self.Q2 = nn.Sequential(
			nn.Linear(feature_dim + action_shape[0], hidden_dim),
			nn.ReLU(inplace=True), nn.Linear(hidden_dim, hidden_dim),
			nn.ReLU(inplace=True), nn.Linear(hidden_dim, 1))

		self.apply(weight_init) # This function already includes orthogonal weight initialization

		# Orthogonal initialization 
		# for m in self.Q1.modules():
		# 	if isinstance(m, (nn.Conv2d, nn.Linear)):
		# 		nn.init.orthogonal_(m.weight)

		# for m in self.Q2.modules():
		# 	if isinstance(m, (nn.Conv2d, nn.Linear)):
		# 		nn.init.orthogonal_(m.weight)

	def forward(self, obs, action):
		h = self.trunk(obs)
		h_action = torch.cat([h, action], dim=-1)
		q1 = self.Q1(h_action)
		q2 = self.Q2(h_action)
		return q1, q2