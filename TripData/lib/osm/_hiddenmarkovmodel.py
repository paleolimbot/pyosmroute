
import numpy as np
from lib.logger import log


def _coorditer(numpyarray):
    it = numpyarray.flat
    while True:
        try:
            c = it.coords
            it.__next__()
            yield c
            pass
        except StopIteration:
            break

class HiddenMarkovModel(object):
    """
    A pure python implementation of a Hidden Markov Model to find the most likely
    series of observations based on a series of emission probabilities and transition probabilities
    with a different transition probability at each time t (this is not as often considered in
    online implementations of the viterbi).
    """

    def __init__(self, eprobs, tprobs):
        self.eprobs = eprobs # eprobs[t][i] = number between 0 and 1
        self.tprobs = tprobs # TransitionProbabilities object
        self.queue = []

    def viterbi(self):

        path = []  # a list of the 'i' chosen for each time 't' and its probability

        for t in range(len(self.eprobs)):
            eprobs = self.eprobs[t]
            tprobs = [self.tprobs[t-1, path[-1][0], j] for j in range(len(eprobs))] \
                if path and None not in path[-1] else np.repeat(1, len(eprobs))
            assert len(eprobs) == len(tprobs)  # has to be true
            probs = [tprobs[i]*eprobs[i] for i in range(len(eprobs))]  # calculate product of emmision and transition
            if np.all(np.array(probs) == 0):
                path.append((None, 0))
                log("Unresolvable break in viterbi at t=%s" % t)
            else:
                path.append((max(enumerate(probs), key=lambda x: x[1])))

        return path

    def viterbi_lookahead(self, lookahead=1):
        path = []  # a list of the 'i' chosen for each time 't' and its probability
        numobs = len(self.eprobs)
        for t in range(numobs):
            if path and None not in path[-1]:
                probs = self._lookahead_matrix(path[-1][0], t, lookahead=min(lookahead, numobs-t-1))
            else:
                probs = np.array(self.eprobs[t])

            if np.all(probs == 0):
                path.append((None, 0))
                log("Unresolvable break in viterbi at t=%s" % t)
            else:
                minind = np.unravel_index(probs.argmax(), probs.shape)
                path.append((minind[0], probs[minind]))

        return path

    def _lookahead_matrix(self, prev_i, t0, lookahead):
        eprobs = np.array([self.eprobs[t0+plust] for plust in range(lookahead+1)])  # list of length lookahead
        probs = np.ndarray([len(subeprobs) for subeprobs in eprobs], dtype=float)
        for index in _coorditer(probs):
            prob = 1
            for plust, j in enumerate(index):
                t = t0 + plust - 1
                i = index[plust-1] if plust != 0 else prev_i
                tprob = self.tprobs[t, i, j]
                eprob = eprobs[plust][j]
                prob *= tprob * eprob
            probs[index] = prob
        return probs
