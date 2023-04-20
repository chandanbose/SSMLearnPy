from sklearn.preprocessing import PolynomialFeatures
import numpy as np


class PolynomialFeaturesWithPattern(PolynomialFeatures):
    def __init__(
            self,
            degree=2,
            interaction_only=False,
            include_bias=True,
            structure=None
            ):
        super().__init__(degree=degree, interaction_only=interaction_only, include_bias=include_bias)
        self.structure = structure

    def fit(self, X, y=None):
        super().fit(X, y)
        return self
    def transform(self, X, y=None):
        transformed = super().transform(X)
        return transformed[:, self.structure]
    
    def fit_transform(self, X, y=None):
        super().fit_transform(X, y)
        return super().transform(X)[:, self.structure]


def complex_polynomial_features(
        y,
        degree = 3,
        skip_linear = False,
        structure = None,
        include_bias = False
        ):
    """
    This is a hack because PolynomialFeatures does not support complex data.

    Parameters:
        y: (n_samples, n_features)
        degree: int
        skip_linear: bool
        structure: (n_polynomial_terms) boolean matrix. If structure[i] = True,
          then we include a term of the form sum_j (y[i]**powers[i,j]) in the polynomial features.
          If structure is None, we include all terms as generated by PolynomialFeatures

    Returns:
        (n_samples, n_polynomial_features): array of polynomial features of y
    """
    size = y.shape[1]
    p = PolynomialFeatures(degree=degree,
                            include_bias=include_bias).fit(np.ones((1, size)))
    powers = p.powers_
    if skip_linear and not include_bias:
        powers = powers[size:, :] 
    if skip_linear and include_bias:
        powers = powers[size+1:, :] # cut the linear part
    features = []
    # structure can be a boolean matrix compatible with powers
    if structure is not None:
        assert structure.shape[0] == powers.shape[0]
        nonzero_entries = powers[structure, :] 
    else:
        nonzero_entries = powers
    for power in nonzero_entries: 
        prod = 1
        for i, p in enumerate(power):
            prod *= y[:,i]**p
        features.append(prod) # this produces rows, so have to transpose in the end
    return np.array(features).T # transpose to get consistent shape with PolynomialFeatures



def get_matrix(l:list):
    return np.concatenate(l, axis=1)

def generate_exponents(
        n_features,
        degree,
        include_bias = False
        ):
    # generate a dummy set of polynomial features to read off the coefficient matrix
    poly = PolynomialFeatures(degree=degree,
                               include_bias=include_bias).fit(np.ones( (1, n_features) ))
    return poly.powers_.T # gives a matrix of shape (n_features, number of monomials of degree <= degree)



def compute_polynomial_map(
        coefficients,
        degree,
        include_bias = False,
        skip_linear = False,
        linear_transform = None
        ):
    """
    Compute the polynomial map corresponding to the given coefficients
    """
    if linear_transform is not None:
        ndofs = int(linear_transform.shape[0] / 2)
        def linear_transform_first(x):
            # the transposes are necessary because a ridge model expects a matrix of shape (n_samples, n_features)
            # because of the projection we need x to be (n_features, n_samples).
            # in order to also produce a matrix of shape (n_samples, n_features), we need to transpose a lot. 
            # TODO: probably there is a smarter way
            y = np.matmul(linear_transform, x) 
            #print(y.shape, x.shape)
            y_features = complex_polynomial_features(y.T, degree=degree, 
                                                             include_bias = include_bias,
                                                             skip_linear = skip_linear)

            #y_features = y_features[:, :ndofs]
            first_half = np.matmul(coefficients, y_features.T)

            return insert_complex_conjugate(first_half).T
        return linear_transform_first
    else: 
        # here x is assumed to be a matrix of shape (n_features, n_samples)
        return lambda x : np.matmul(coefficients,
                                    complex_polynomial_features(x.T, degree=degree, 
                                                                include_bias = include_bias,
                                                                skip_linear=skip_linear).T).T 

def insert_complex_conjugate(x):
    return np.concatenate((x, np.conj(x)), axis = 0)


def unpack_coefficient_matrices_from_vector(
    z,
    n_coefs_1,
    n_features,
    n_targets
):
    """Helper function for fit_reduced_coords_and_parametrization() and create_normalform_transform_objective().
    Reshapes a long vector (variable for an optimization). Into _two_ matrices: 
    Parameters:
        z: (n_optim) array: vector of optimization variables
        n_coefs: int: number of optimization variables that should be folded into the first matrix.
                     All other variables are folded into the second matrix.
        n_features: int: 
        n_targets: int: The first matrix is folded into a matrix of shape (n_targets, n_features)
                        The second matrix is folded into a matrix of shape (n_targets, n_features_2)
                        where n_nonlinear_features = (n_optim - n_coefs_1)/n_targets
    Returns:
        matrix_1: (n_targets, n_features) array
        matrix_2: (n_targets, n_features_2) array, n_features_2 = (n_optim - n_coefs_1)/n_targets
    """
    matrix_1 = z[:n_coefs_1].reshape(n_targets, n_features)
    n_coefs_2 = z.shape[0] - n_coefs_1
    n_features_2 = int(n_coefs_2/n_targets)
    matrix_2 = z[n_coefs_1:].reshape(n_targets, n_features_2)
    return matrix_1, matrix_2