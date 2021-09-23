import pickle

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from utils.train_synthetic import load_synthetic_results


def get_joint_coverages(baseline, experiment):
    """ Returns joint horizon coverages for each dataset setting. """
    coverages = []
    for seed in range(5):
        dataset_coverages = []
        results = load_synthetic_results(experiment=experiment,
                                         baseline=baseline, seed=seed)
        for result in results:
            dataset_coverages.append(
                result['Mean joint coverage'] * 100)
        coverages.append(dataset_coverages)
    coverages = np.array(coverages)
    return zip(coverages.mean(axis=0), coverages.std(axis=0))


def get_interval_widths(baseline, experiment):
    # TODO get interval width for and horizon (col) for an
    #  experiment accounting for the dataset settings (row) ± over seeds and
    #  return as dataframe

    wws = []  # array containing interval widths for horizon=5 for each seed
    for seed in range(5):
        ws = []
        results = load_synthetic_results(experiment=experiment,
                                         baseline=baseline, seed=seed)
        for result in results:  # for each setting
            # for the data setttings (increasing time-dependent noise)
            widths = result['Mean confidence interval widths']  # [1xhorizon]
            # averages across the horizon, elements of ws represent different experiment mode
            ws.append(
                '{:.2f} \\(\\pm\\) {:.2f}'.format(widths.mean(), widths.std()))
        wws.append(ws)

    # rows denote increasing time-dependent noise configuration, columns denote seeds
    for i in range(1):
        #         print('{} & {} & {} & {} & {}'.format(wws[0][i], wws[1][i], wws[2][i], wws[3][i], wws[4][i]))
        for j in range(5):
            print(wws[j][i])
    print()


def plot_timeseries(experiment, baseline, seed=0, index=None,
                    forecast_only=False, figsize=(28, 4), figure_name=None):
    # TODO cleanup
    plt.rcParams.update({
        "text.usetex": False,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica"]})
    plt.rcParams.update({'axes.titlesize': 16,
                         'axes.labelsize': 13})

    datasets = []
    for i in ([2, 10] if experiment == 'periodic' else range(1, 6)):
        with open('processed_data/synthetic-{}-{}-{}.pkl'.format(experiment, i,
                                                                 seed),
                  'rb') as f:
            datasets.append(pickle.load(f))

    with open('saved_results/{}-{}-{}.pkl'.format(experiment, baseline, seed),
              'rb') as f:
        all_results = pickle.load(f)

    fig, axs = plt.subplots(nrows=1, ncols=len(datasets), figsize=figsize,
                            sharey=True)

    for j, ax in enumerate(axs.flat):
        _, dataset = datasets[j]
        results = all_results[j]

        X, Y, _ = dataset

        if index is None:
            index = range(len(X))
        i = np.random.choice(index)

        # Derive unpadded sequences and targets
        sequence, target = X[i], Y[i]

        horizon = len(target)
        length = len(sequence)

        if not forecast_only:
            # (Scatter)plot of the time series
            ax.plot(range(1, length + 1), sequence, color="black")

            # Prediction start vertical
            ax.axvline(length, linestyle="--", color="black")

        ax.scatter(range(length + 1, length + horizon + 1), target,
                   color="black")

        # Interval boundaries
        upper_limit = results['Upper limit']
        lower_limit = results['Lower limit']

        lower = [sequence[-1].item()] + lower_limit[i].flatten().tolist()
        upper = [sequence[-1].item()] + upper_limit[i].flatten().tolist()
        preds = [sequence[-1].item()] + results['Point predictions'][
            i].flatten().tolist()

        ax.fill_between(range(length, length + horizon + 1), lower, upper,
                        color="r", alpha=0.25)
        ax.plot(range(length, length + horizon + 1), lower, linestyle="--",
                color="r")
        ax.plot(range(length, length + horizon + 1), upper, linestyle="--",
                color="r")
        ax.plot(range(length, length + horizon + 1), preds, linestyle="--",
                linewidth=3, color="r")

        if j == 0:
            ax.set(ylabel='Prediction')
        ax.set(xlabel='Time step')
        if experiment == 'time_dependent':
            ax.set(title='$\sigma_t^2 =${:.1f}$t$'.format((j + 1) * 0.1))

    plt.subplots_adjust(left=0.1,
                        bottom=0.1,
                        right=0.9,
                        top=0.9,
                        wspace=0.1,
                        hspace=0.4)

    if figure_name is not None:
        plt.savefig('{}.png'.format(figure_name), bbox_inches='tight')
    plt.show()

# TODO compute valid horizons

# TODO compute interval widths vs coverage

# TODO demonstrate sample complexity
