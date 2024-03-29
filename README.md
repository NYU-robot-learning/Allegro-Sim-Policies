# Allegro-Sim-Policies

This codebase has been released as a part of [OpenTeach](https://arxiv.org/abs/2403.07870)

Clone the repository using the following command.

git clone https://github.com/NYU-robot-learning/Allegro-Sim-Policies.git

Installation

`mamba env create -f conda_env.yml`

Install the Codebase as a module using 

`pip install -e .`

Collect Demos using OpenTeach.

##### How to train policies with FISH using demos from Open-Teach?

1. Change the path in configs to the path where you saved your data.
2. Preprocess the data using the following command `python3 preprocess.py`
3. Choose the path you have collected data in configs in data_dir:. Choose the data representations you want to use for training from `image , allegro`
4. Once preprocessed you can train the Vision and tactile encoder using python train.py. You can edit train.yaml accordingly with the choice of encoder, rl_learners, rewarders and optimizers.
5. After training the Vision and tactile encoders you can start the offset learning following TAVI using `python train_online_sim.py`. You can set the task, base_policy,agent, explorer and rewarder. configs

### Citation
If you use this repo in your research, please consider citing the paper as follows:
```@misc{iyer2024open,
      title={OPEN TEACH: A Versatile Teleoperation System for Robotic Manipulation}, 
      author={Aadhithya Iyer and Zhuoran Peng and Yinlong Dai and Irmak Guzey and Siddhant Haldar and Soumith Chintala and Lerrel Pinto},
      year={2024},
      eprint={2403.07870},
      archivePrefix={arXiv},
      primaryClass={cs.RO}
}