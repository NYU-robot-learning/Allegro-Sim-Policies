# Gym implementation of our robotic setup

from collections import deque
from typing import Any, NamedTuple
# from typing import Any
# from allegro_sim.utils import Any, NamedTuple

import gym
#import dexterous_env
from gym import  spaces

import dm_env
import numpy as np
from dm_env import StepType, specs, TimeStep

from isaacgym import gymapi
# from dm_control.utils import rewards

class RGBArrayAsObservationWrapper(dm_env.Environment):
	"""
	Use env.render(rgb_array) as observation
	rather than the observation environment provides

	From: https://github.com/hill-a/stable-baselines/issues/915
	"""
	def __init__(self, env, width=84, height=84):
		self._env = env
		self._width = width
		self._height = height
		self._env.reset()

		dummy_obs = self._env.render(mode="rgb_array", width=self._width, height=self._height)
		#print(dummy_obs.dtype)
		print('dummy_obs.shape: {}'.format(dummy_obs.shape))
		self.observation_space  = spaces.Box(low=0, high=255, shape=(height, width, 3), dtype=dummy_obs.dtype)
		# print('self.observation_space.shape: {}'.format(self.observation_space))
		self.action_space = self._env.action_space
		
		# Action spec
		wrapped_action_spec = self.action_space
		if not hasattr(wrapped_action_spec, 'minimum'):
			wrapped_action_spec.minimum = -np.ones(wrapped_action_spec.shape)
		if not hasattr(wrapped_action_spec, 'maximum'):
			wrapped_action_spec.maximum = np.ones(wrapped_action_spec.shape)
		self._action_spec = specs.BoundedArray(wrapped_action_spec.shape,
										np.float32,
										wrapped_action_spec.minimum,
										wrapped_action_spec.maximum,
										'action')
		#Observation spec
		self._obs_spec = {}
		self._obs_spec['pixels'] = specs.BoundedArray(shape=self.observation_space.shape,
													  dtype=np.uint8,
													  minimum=0,
													  maximum=255,
													  name='observation')

		


	def reset(self, **kwargs):
		obs = {}
		obs = self._env.reset(**kwargs)
		obs['pixels'] = obs['pixels'].astype(np.uint8)
		obs['goal_achieved'] = False
		# print("RGB observation resetted")
		return obs

	def step(self, action):
		obs, reward, done, _, info = self._env.step(action) # It's returning truncated
		obs['pixels'] = obs['pixels'].astype(np.uint8)
		# We will be receiving 
		obs['goal_achieved'] = info['is_success']
		return obs, reward, done, info

	def observation_spec(self):
		return self._obs_spec

	def action_spec(self):
		return self._action_spec

	def render(self, mode="rgb_array", width=256, height=256):
		return self._env.render(mode="rgb_array", width=width, height=height)

	def __getattr__(self, name):
		return getattr(self._env, name)
	
# It should receive the tactile embeddings and add that as a spec to the observations
class TactileReprAsObservationWrapper(dm_env.Environment):
	def __init__(self, env, tactile_embedding_dim=1024):
		self._env = env 
		self._tactile_size = tactile_embedding_dim

		self._env.reset()

		# Add the tactile obs_spec
		self._obs_spec = self._env.observation_spec()
		self._obs_spec['tactile'] = specs.Array(
			shape = (self._tactile_size,),
			dtype = np.float32, # NOTE: is this a problem?
			name = 'tactile' # We will receive the representation directly
		)

	def reset(self, **kwargs):
		obs = {}
		obs = self._env.reset(**kwargs)
		obs['tactile'] = obs['tactile'].astype(np.float32) # NOTE: you might need to change this after you implement the environment
		return obs

	def step(self, action):
		obs, reward, done, info = self._env.step(action)
		obs['tactile'] = obs['tactile'].astype(np.float32)	
		return obs, reward, done, info

	def observation_spec(self):
		return self._obs_spec

	def action_spec(self):
		return self._env.action_spec()

	def render(self, mode="rgb_array", width=256, height=256): # NOTE: We could choose to render tactile as well 
		return self._env.render(mode="rgb_array", width=width, height=height)

	def __getattr__(self, name):
		return getattr(self._env, name)

class RobotFeaturesAsObservationWrapper(dm_env.Environment):
	def __init__(self, env, feature_dim=23):
		self._env = env
		self.dim = feature_dim

		self._env.reset()

		# Add the features obs spec
		self._obs_spec = self._env.observation_spec()
		self._obs_spec['features'] = specs.Array(
			shape = (feature_dim,),
			dtype = np.float32,
			name = 'features'
		)

	def reset(self, **kwargs):
		obs = self._env.reset(**kwargs)
		print(obs['features'])
		obs['features'] = obs['features'].astype(np.float32)
		
		return obs
	
	def step(self, action):
		obs, reward, done, info = self._env.step(action)
		obs['features'] = obs['features'].astype(np.float32)
		return obs, reward, done, info

	def observation_spec(self):
		return self._obs_spec

	def action_spec(self):
		return self._env.action_spec()

	def render(self, mode="rgb_array", width=256, height=256): # NOTE: We could choose to render tactile as well 
		return self._env.render(mode="rgb_array", width=width, height=height)

	def __getattr__(self, name):
		return getattr(self._env, name)

class ExtendedTimeStep(NamedTuple):

	# def __init__(self,**kwargs):
	# 	self.__dict__.update(**kwargs)
	step_type: Any
	reward: Any
	discount: Any
	action: Any
	observation: Any
	base_action: Any

	def first(self):
		return self.step_type == StepType.FIRST

	def mid(self):
		return self.step_type == StepType.MID

	def last(self):
		return self.step_type == StepType.LAST

	# def __getitem__(self, attr):
	# 	return getattr(self, attr)
	
	# def __getitem__(self, attr):
	# 	print('ATTR IN EXTENDEDTIMESTEP: {}'.format(attr))
	# 	# print('self.dict in getitem: {}'.format(self.__dict__))
	# 	# print(self[attr])
	# 	# return getattr(self, 'observation')
	# 	# return None
	# 	print(self.attr)


class ActionRepeatWrapper(dm_env.Environment):
	def __init__(self, env, num_repeats):
		self._env = env
		self._num_repeats = num_repeats
		
	def step(self, action):
		reward = 0.0
		discount = 1.0
		for i in range(self._num_repeats):
			time_step = self._env.step(action)
			reward += (time_step.reward or 0.0) * discount
			discount *= time_step.discount
			if time_step.last():
				break

		return time_step._replace(reward=reward, discount=discount)

	def observation_spec(self):
		return self._env.observation_spec()

	def action_spec(self):
		return self._env.action_spec()

	def reset(self):
		return self._env.reset()

	def __getattr__(self, name):
		return getattr(self._env, name)

class FrameStackWrapper(dm_env.Environment):
	def __init__(self, env, num_frames):
		self._env = env
		self._num_frames = num_frames
		self._frames = deque([], maxlen=num_frames)
		# self._tactile_frames = deque([], maxlen=num_frames)
		self._features_frames = deque([], maxlen=num_frames)

		wrapped_obs_spec = env.observation_spec()
		print(wrapped_obs_spec)
		pixels_shape = wrapped_obs_spec['pixels'].shape
		if len(pixels_shape) == 4:
			pixels_shape = pixels_shape[1:]
		self._obs_spec = {}
		self._obs_spec['pixels'] = specs.BoundedArray(shape=np.concatenate(
			[[pixels_shape[2] * num_frames], pixels_shape[:2]], axis=0),
											dtype=np.uint8,
											minimum=0,
											maximum=255,
											name='pixels')
		
		print('self.obs_spec[pixels]: {}'.format(self._obs_spec['pixels']))
		
		#tactile_shape = wrapped_obs_spec['tactile'].shape
		# self._obs_spec['tactile'] = specs.Array(
		# 	shape = (num_frames * tactile_shape[0],),
		# 	dtype = np.float32, 
		# 	name = 'tactile'
		# )
		features_shape = wrapped_obs_spec['features'].shape
		self._obs_spec['features'] = specs.Array(
			shape = (num_frames * features_shape[0],),
			dtype = np.float32, 
			name = 'features'
		)

	def _transform_observation(self, time_step):
		assert len(self._frames) == self._num_frames
		#assert len(self._tactile_frames) == self._num_frames
		assert len(self._features_frames) == self._num_frames
		obs = {}
		obs['pixels'] = np.concatenate(list(self._frames), axis=0)
		#obs['tactile'] = np.concatenate(list(self._tactile_frames), axis=0)
		obs['features'] = np.concatenate(list(self._features_frames), axis=0)

		obs['goal_achieved'] = time_step.observation['goal_achieved']
		return time_step._replace(observation=obs)

	def _extract_pixels(self, time_step):
		pixels = time_step.observation['pixels']
		print('extract_pixels.shape: {}'.format(pixels.shape))
		# remove batch dim
		if len(pixels.shape) == 4:
			pixels = pixels[0]
		# return pixels.transpose(2, 0, 1).copy()
		return pixels.copy()

	def _extract_tactile_repr(self, time_step):
		tactile_repr = time_step.observation['tactile']
		return tactile_repr # Add a new dimension as the `batch` for frame stacking

	def reset(self):
		time_step = self._env.reset()
		pixels = self._extract_pixels(time_step)
		#tactiles = self._extract_tactile_repr(time_step)
		features = time_step.observation['features']
		for _ in range(self._num_frames):
			self._frames.append(pixels)
			#self._tactile_frames.append(tactiles)
			self._features_frames.append(features)

		return self._transform_observation(time_step)

	def step(self, action):
		time_step = self._env.step(action)
		pixels = self._extract_pixels(time_step)
		#tactiles = self._extract_tactile_repr(time_step)
		features = time_step.observation['features']
		self._frames.append(pixels)
		# self._tactile_frames.append(tactiles)
		self._features_frames.append(features)
		return self._transform_observation(time_step)

	def observation_spec(self):
		return self._obs_spec

	def action_spec(self):
		return self._env.action_spec()

	def __getattr__(self, name):
		return getattr(self._env, name)


class ActionDTypeWrapper(dm_env.Environment):
	def __init__(self, env, dtype):
		self._env = env
		self._discount = 1.0

		# Action spec
		wrapped_action_spec = env.action_space
		if not hasattr(wrapped_action_spec, 'minimum'):
			wrapped_action_spec.minimum = -np.ones(wrapped_action_spec.shape)
		if not hasattr(wrapped_action_spec, 'maximum'):
			wrapped_action_spec.maximum = np.ones(wrapped_action_spec.shape)
		self._action_spec = specs.BoundedArray(wrapped_action_spec.shape,
										np.float32,
										wrapped_action_spec.minimum,
										wrapped_action_spec.maximum,
										'action')

	def step(self, action):
		action = action.astype(self._env.action_space.dtype)
		# Make time step for action space
		observation, reward, done, info = self._env.step(action)
		reward = reward + 1
		step_type = StepType.LAST if done else StepType.MID
		return TimeStep(
					step_type=step_type,
					reward=reward,
					discount=self._discount,
					observation=observation
				)

	def observation_spec(self):
		return self._env.observation_spec()

	def action_spec(self):
		return self._action_spec

	def reset(self):
		obs = self._env.reset()
		return TimeStep( # This only sort of wraps everything in a timestep
					step_type=StepType.FIRST,
					reward=0,
					discount=self._discount,
					observation=obs
				)

	def __getattr__(self, name):
		return getattr(self._env, name)


class ExtendedTimeStepWrapper(dm_env.Environment):
	def __init__(self, env):
		self._env = env

	def reset(self):
		time_step = self._env.reset()
		return self._augment_time_step(time_step)

	def step(self, action, base_action): # NOTE: Here this is only for returning the base action as a part of the implementation as well
		time_step = self._env.step(action)
		return self._augment_time_step(time_step, action, base_action)

	def _augment_time_step(self, time_step, action=None, base_action=None):
		print("Wrapped in extended timestepwrapper")
		if action is None:
			action_spec = self.action_spec()
			action = np.zeros(action_spec.shape, dtype=action_spec.dtype)
			base_action = np.zeros(action_spec.shape, dtype=action_spec.dtype)
		# print("Observation in the extendedtimestep wrapper", time_step.observation)
		# print('time_step.observation[pixels].shape: {}'.format(time_step.observation['pixels'].shape))
		return ExtendedTimeStep(observation=time_step.observation,
								step_type=time_step.step_type,
								action=action,
								base_action=base_action,
								reward=time_step.reward or 0.0,
								discount=time_step.discount or 1.0)

	def _replace(self, time_step, observation=None, action=None, reward=None, discount=None):
		if observation is None:
			observation = time_step.observation
		if action is None:
			action = time_step.action
		if base_action is None:
			base_action = time_step.base_action
		if vinn_next_action is None:
			vinn_next_action = time_step.vinn_next_action
		if reward is None:
			reward = time_step.reward
		if discount is None:
			discount = time_step.discount
		return ExtendedTimeStep(observation=observation,
								step_type=time_step.step_type,
								action=action,
								reward=reward,
								discount=discount)


	def observation_spec(self):
		return self._env.observation_spec()

	def action_spec(self):
		return self._env.action_spec()

	def __getattr__(self, name):
		return getattr(self._env, name)


def make(name, tactile_out_dir, tactile_model_type, host_address, camera_num, height, width, tactile_dim, frame_stack, action_repeat, action_type):
	env = gym.make(
		name,
		tactile_out_dir = tactile_out_dir,
		tactile_model_type = tactile_model_type,
		host_address = host_address,
		camera_num = camera_num,
		height = height,
		width = width,
		action_type = action_type
	)
	# env.seed(seed)
	
	# # add wrappers
	print("Camera num while creating env", camera_num)
	env = RGBArrayAsObservationWrapper(env, width=width, height=height)
	#env = TactileReprAsObservationWrapper(env, tactile_embedding_dim=tactile_dim)
	# feature_dim = 19 if action_type == 'fingertip' else 23
	env = RobotFeaturesAsObservationWrapper(env)
	env = ActionDTypeWrapper(env, np.float32)
	env = ActionRepeatWrapper(env, action_repeat)
	env = FrameStackWrapper(env, frame_stack)
	env = ExtendedTimeStepWrapper(env)
	return env

def make_sim(num_per_row,spacing,show_axis, env_suite, control_mode, name, tactile_out_dir, tactile_model_type, host_address, camera_num, height, width, tactile_dim, frame_stack, action_repeat, action_type):
	print("Name of gym environment",name)
	env= gym.make(name,
		num_per_row=num_per_row,
		spacing=spacing,
		show_axis=show_axis,
		env_suite=env_suite,control_mode=control_mode,tactile_out_dir=tactile_out_dir, tactile_model_type=tactile_model_type, host_address=host_address, camera_num=camera_num, height=height, width=width, action_type=action_type)
	
	print("Gym Env created")
	env = RGBArrayAsObservationWrapper(env, width=width, height=height)
	print("RGB wrapper created")
	#env = TactileReprAsObservationWrapper(env, tactile_embedding_dim=tactile_dim)
	# feature_dim = 19 if action_type == 'fingertip' else 23
	env = RobotFeaturesAsObservationWrapper(env)
	print("Feature Wrapper created")
	env = ActionDTypeWrapper(env, np.float32)
	print("Action Dtype Wrapper")
	env = ActionRepeatWrapper(env, action_repeat)

	print("Action Repeat Wrapper")
	env = FrameStackWrapper(env, frame_stack)
	print("Frame stack Wrapper")
	env = ExtendedTimeStepWrapper(env)

	return env

if __name__ == '__main__':
	env = make(
		name = 'BowlUnstacking-v1',
		tactile_out_dir = '/home/aadhithya/tactile-learning/allegro_sim/out/2023.01.28/12-32_tactile_byol_bs_512_tactile_play_data_alexnet_pretrained_duration_120',
		host_address = '172.24.71.211',
		camera_num = 0, 
		height = 224, 
		width = 224,
		tactile_dim=1024, 
		frame_stack=1,
		action_repeat=1,
		tactile_model_type='byol',
		action_type='joint'
		# seed=42
	)

	import random
	import glob
	
	from allegro_sim.utils import load_data
	from openteach.robot.allegro.allegro_kdl import AllegroKDL
	from openteach.utils.timer import FrequencyTimer

	roots = sorted(glob.glob('/home/irmak/Workspace/Holo-Bot/extracted_data/bowl_picking/after_rss/demonstration_*'))
	data = load_data(roots=roots, demos_to_use=[22,24,26,34,28,29])
	kdl_solver = AllegroKDL()
	current_step = 0
	timer = FrequencyTimer(15)
	while (True):
		timer.start_loop()

		# Get a random action and apply it to see the step function works
		demo_id, allegro_action_id = data['allegro_actions']['indices'][current_step]
		allegro_joint_action = data['allegro_actions']['values'][demo_id][allegro_action_id]
		# allegro_fingertip_action = kdl_solver.get_fingertip_coords(allegro_joint_action)

		# demo_id, allegro_id = data['allegro_tip_states']['indices'][current_step]
		# allegro_fingertip_action = data['allegro_tip_states']['values'][demo_id][allegro_id]

		_, kinova_id = data['kinova']['indices'][current_step]
		kinova_action = data['kinova']['values'][demo_id][kinova_id]

		action = np.concatenate([allegro_joint_action, kinova_action], 0)

		# _ = input(
		# 	f'Press keyboard to apply the action {action}'
		# )

		time_step = env.step(action=action, base_action=np.zeros(23))
		print('time_step: {}'.format(time_step))
		current_step += 1

		timer.end_loop()