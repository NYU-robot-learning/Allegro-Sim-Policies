# Rewarder module for sinkhorn cosine

import numpy as np
import torch 
import sys

from allegro_sim.utils import cosine_distance, optimal_transport_plan

from .rewarder import Rewarder

class SinkhornCosine(Rewarder):
    def __init__(
            self,
            exponential_weight_init=False, 
            **kwargs
    ):
        super().__init__(**kwargs)
        self.exponential_weight_init = exponential_weight_init

    def get(self, obs): 
        # Get representations 
        episode_repr, expert_reprs = self.get_representations(obs)

        # print('episode_repr.shape: {}, expert_reprs.shape: {}'.format(episode_repr.shape, expert_reprs.shape))

        all_rewards = []
        cost_matrices = []
        best_reward_sum = - sys.maxsize
        for expert_id, expert_repr in enumerate(expert_reprs):
            # expert_repr = expert_repr.unsqueeze(0) # It should have dimension 1 for the 1st dimension
            print('expert_repr.shape: {}, episode_Repr.shape: {}'.format(
                expert_repr.shape, episode_repr.shape
            ))
            cost_matrix = cosine_distance(
                    episode_repr, expert_repr)  # Get cost matrix for samples using critic network.
            transport_plan = optimal_transport_plan(
                episode_repr, expert_repr, cost_matrix, method='sinkhorn',
                niter=100, exponential_weight_init=self.exponential_weight_init).float()  # Getting optimal coupling
            rewards = -self.sinkhorn_rew_scale * torch.diag(
                torch.mm(transport_plan,
                            cost_matrix.T)).detach().cpu().numpy()
            
            all_rewards.append(rewards)
            sum_rewards = np.sum(rewards)
            cost_matrices.append(cost_matrix)
            if sum_rewards > best_reward_sum:
                best_reward_sum = sum_rewards 
                best_expert_id = expert_id
        print("All rewards: ", all_rewards)
        final_reward = all_rewards[best_expert_id]
        final_cost_matrix = cost_matrices[best_expert_id]

        return final_reward, final_cost_matrix, best_expert_id

