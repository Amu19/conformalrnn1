import gc
import pickle

import numpy as np
import torch

from models.cornn import CoRNN
from models.rnn import RNN
from models.bjrnn import RNN_uncertainty_wrapper
from utils.data_processing_synthetic import get_synthetic_splits
from utils.performance import evaluate_performance


def train_conformal_forecaster(noise_mode='time-dependent',
                               epochs=1000,  # LSTM parameters
                               batch_size=100,
                               embedding_size=20,
                               coverage=0.9,
                               lr=0.01,
                               retrain=False,
                               save_model=False,
                               save_results=True,
                               rnn_mode='LSTM'):
    if retrain:
        if noise_mode == 'periodic':
            horizon = 10
        else:
            horizon = 5

        horizons = [100]

        ranges = {
            'periodic': [2, 10],
            'time-dependent': range(1, 6),
            'static': range(1, 6),
            'long-horizon': [100],
        }

        datasets = get_synthetic_splits(noise_mode=noise_mode, conformal=True)
        results = []

        for i, dataset in enumerate(datasets):
            if noise_mode == 'long-horizon':
                horizon = horizons[i]

            train_dataset, calibration_dataset, test_dataset = dataset

            model = CoRNN(embedding_size=embedding_size, horizon=horizon,
                          error_rate=1 - coverage, mode=rnn_mode)
            model.fit(train_dataset, calibration_dataset, epochs=epochs, lr=lr,
                      batch_size=batch_size)
            if save_model:
                torch.save(model, 'saved_models/{}_{}_{}_{}.pt'.format(
                    noise_mode, 'CoRNN', model.mode, ranges[noise_mode][i]))

            independent_coverages, joint_coverages, intervals = \
                model.evaluate_coverage(test_dataset)
            mean_independent_coverage = torch.mean(
                independent_coverages.float(),
                dim=0)
            mean_joint_coverage = torch.mean(joint_coverages.float(),
                                             dim=0).item()
            interval_widths = (intervals[:, 1] - intervals[:, 0]).squeeze()
            point_predictions, errors = \
                model.get_point_predictions_and_errors(test_dataset)

            result = {'Point predictions': point_predictions,
                      'Errors': errors,
                      'Independent coverage indicators':
                          independent_coverages.squeeze(),
                      'Joint coverage indicators':
                          joint_coverages.squeeze(),
                      'Upper limit': intervals[:, 1],
                      'Lower limit': intervals[:, 0],
                      'Mean independent coverage':
                          mean_independent_coverage.squeeze(),
                      'Mean joint coverage': mean_joint_coverage,
                      'Confidence interval widths': interval_widths,
                      'Mean confidence interval widths': interval_widths.mean(
                          dim=0)}

            results.append(result)

        if save_results:
            with open('saved_results/{}_{}.pkl'.format(noise_mode, 'CoRNN'),
                      'wb') as f:
                pickle.dump(results, f, protocol=pickle.HIGHEST_PROTOCOL)
    else:
        with open('saved_results/{}_{}.pkl'.format(noise_mode, 'CoRNN'),
                  'rb') as f:
            results = pickle.load(f)

    return results


def train_blockwise_forecaster(noise_mode='time-dependent',
                               epochs=10,  # LSTM parameters
                               batch_size=100,
                               embedding_size=20,
                               coverage=0.9,
                               lr=0.01,
                               retrain=False):
    if retrain:
        params = {'epochs': epochs,
                  'batch_size': batch_size,
                  'embedding_size': embedding_size,
                  'coverage': coverage,
                  'lr': lr,
                  'n_steps': 10,
                  'input_size': 1,
                  'mode': 'LSTM'}

        if noise_mode == 'periodic':
            length = 20
            horizon = 10
        else:
            length = 10
            horizon = 5

        params['max_steps'] = length
        params['output_size'] = horizon

        datasets = get_synthetic_splits(conformal=False, horizon=horizon)
        results = []
        for dataset in datasets:
            train_dataset, _, test_dataset = dataset

            model = RNN(**params)
            model.fit(train_dataset[0], train_dataset[1])
            model_ = RNN_uncertainty_wrapper(model)
            result = evaluate_performance(model_, test_dataset[0],
                                          test_dataset[1],
                                          coverage=params['coverage'],
                                          error_threshold="Auto")

            results.append(result)
            del model_

            with open('saved_results/{}_{}.pkl'.format(noise_mode, 'BJRNN'),
                      'wb') as f:
                pickle.dump(results, f, protocol=pickle.HIGHEST_PROTOCOL)
    else:
        with open('saved_results/{}_{}.pkl'.format(noise_mode, 'BJRNN'),
                  'rb') as f:
            results = pickle.load(f)

    return results


def train_bjrnn():
    def get_coverage(intervals_, target, coverage_mode='joint'):
        lower, upper = intervals_[0], intervals_[1]

        horizon_coverages = np.logical_and(target >= lower, target <= upper)
        if coverage_mode == 'independent':
            return horizon_coverages
        else:  # joint coverage
            return np.all(horizon_coverages, axis=0)

    params = dict({"input_size": 1,  # RNN parameters
                   "epochs": 1000,
                   "n_steps": 5,
                   "batch_size": 100,
                   "embedding_size": 20,
                   "max_steps": 10,
                   "output_size": 5,
                   "coverage": 0.9,
                   "lr": 0.01,
                   "mode": "RNN"})

    results = []
    for i in range(1, 6):
        with open('processed_data/synthetic_{}_raw_{}.pkl'.format(
                'time-dependent', i),
                'rb') as f:
            train_dataset, calibration_dataset, test_dataset = \
                pickle.load(f)
        X_train, Y_train = train_dataset
        X_test, Y_test = test_dataset

        RNN_model = RNN(**params)
        RNN_model.fit(X_train, Y_train)

        RNN_model_ = RNN_uncertainty_wrapper(RNN_model)

        coverages = []
        intervals = []

        for j, (x, y) in enumerate(zip(X_test, Y_test)):
            y_pred, y_l_approx, y_u_approx = RNN_model_.predict(x)
            interval = np.array([y_l_approx[0], y_u_approx[0]])
            covers = get_coverage(interval, y.flatten().detach().numpy())
            coverages.append(covers)
            intervals.append(interval)
            if j % 50 == 0:
                print('Example {}'.format(j))

        mean_coverage = np.mean(coverages)
        np_intervals = np.array(intervals)
        interval_widths = (np_intervals[:, 1] - np_intervals[:, 0]).mean(axis=0)

        result = {'coverages': coverages,
                  'intervals': intervals,
                  'mean_coverage': mean_coverage,
                  'interval_widths': interval_widths}

        print('Model {}:\tcoverage: {}\twidths: {}'.format(i, result[
            'mean_coverage'], result['interval_widths']))
        results.append(result)
        del RNN_model
        del RNN_model_
        gc.collect()

    with open('saved_results/time-dependent_BJRNN.pkl', 'wb') as output:
        pickle.dump(results, output, pickle.HIGHEST_PROTOCOL)

    return results


if __name__ == "__main__":
    train_bjrnn()
