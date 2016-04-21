
import numpy as np
from ..logger import log


def _coorditer(numpyarray):
    it = numpyarray.flat
    while True:
        try:
            c = it.coords
            next(it)
            yield c
            pass
        except StopIteration:
            break


def _unravel_index(k, shape):
    # pypy does not implement np.unravel_index(index, shape)
    if len(shape) == 1:
        return int(k)
    elif len(shape) == 2:
        ncol = shape[1]
        return int(k/ncol), int(k%ncol)
    else:
        raise NotImplementedError("Custom _unravel_index not available for shape > 2 dimensions")


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
        """
        A possibly erroneous implementation of the viterbi algorithm. Navigates the HMM by choosing the highest
        emission proability * transition probability from the last point TO the points at time t for all t.
        :return: A list of 2 tuples, each of which contain the i chosen at each t and the probability product.
        """
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
        """
        A slightly modified version of the viterbi above, using a n-dimentional array to 'look a head' and choose
        the option that will lead to the best future outcome. Passing lookahead=0 will result in an identical
        result as viterbi() above.
        :param lookahead: The number of steps to look forward from t
        :return: A list of 2 tuples, each of which contain the i chosen at each t and the probability product.
        """
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
                # minind = np.unravel_index(probs.argmax(), probs.shape)
                minind = _unravel_index(probs.argmax(), probs.shape)
                path.append((int(minind[0]) if type(minind) != int else minind, probs[minind]))

        return path

    def _lookahead_matrix(self, prev_i, t0, lookahead):
        """
        Creates an n-dimentional array with dimentions such that probs[t][t+1][t+2]...[t+lookahead] = the probability
        product for that chain.
        :param prev_i: The previous i.
        :param t0: The t at which we are trying to make a choice.
        :param lookahead: The number of steps to look ahead
        :return: An n-dimentional array such that probs[t][t+1][t+2]...[t+lookahead] = the probability to be maximized
        """
        eprobs = [self.eprobs[t0+plust] for plust in range(lookahead+1)] # list of length lookahead
        probs = np.ndarray(shape=[len(subeprobs) for subeprobs in eprobs], dtype=float)
        for index in _coorditer(probs):
            prob = 1
            for plust, j in enumerate(index):
                t = t0 + plust - 1
                i = int(index[plust-1] if plust != 0 else prev_i)
                tprob = self.tprobs[t, i, j]
                eprob = eprobs[plust][j]
                prob *= tprob * eprob
            probs[index] = prob
        return probs
