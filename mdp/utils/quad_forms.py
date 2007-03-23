import mdp
from routines import refcast
numx = mdp.numx

# 10 times machine eps
epsilon = 10*numx.finfo(numx.double).eps

class QuadraticForm(object):
    """
    Define an inhomogeneous quadratic form as 1/2 x'Hx + f'x + c .
    This class implements the quadratic form analysis methods
    presented in:

    Berkes, P. and Wiskott, L. (2006). On the analysis and interpretation
    of inhomogeneous quadratic forms as receptive fields. Neural
    Computation, 18(8): 1868-1895.
    """

    def __init__(self, H, f=None, c=None, dtype='d'):
        """
        The quadratic form is defined as 1/2 x'Hx + f'x + c .
        'dtype' specifies the numerical type of the internal structures.
        """
        local_eps = 10*numx.finfo(numx.dtype(dtype)).eps
        # check that H is almost symmetric
        if not numx.allclose(H,H.T,rtol=100*local_eps, atol=local_eps):
            raise mdp.MDPException, 'H does not seem to be symmetric'
        
        self.H = refcast(H, dtype)
        if f is None: f = numx.zeros((H.shape[0],), dtype=dtype)
        if c is None: c = 0
        self.f = refcast(f, dtype)
        self.c = c
        self.dtype = dtype

    def apply(self, x):
        """Apply the quadratic form to the input vectors.
        Return 1/2 x'Hx + f'x + c ."""
        x = numx.atleast_2d(x)
        return 0.5*(mdp.utils.mult(x, self.H.T)*x).sum(axis=1) + \
               mdp.utils.mult(x, self.f) + self.c
        
    def get_extrema(self, norm, tol = 1.E-4):
        """
        Find the input vectors xmax and xmin with norm 'nrm' that maximize
        or minimize the quadratic form.

        tol: norm error tolerance
        """
        H, f, c = self.H, self.f, self.c
        if max(abs(f)) < numx.finfo(self.dtype).eps:
            E, W = mdp.utils.symeig(H)
            xmax = W[:,-1]*norm
            xmin = W[:,0]*norm
        else:    
            H_definite_positive, H_definite_negative = False, False
            E = mdp.utils.symeig(H, eigenvectors=0, overwrite=0)
            if E[0] >= 0:
                # H is positive definite
                H_definite_positive = True
            elif E[-1] <= 0:
                # H is negative definite
                H_definite_negative = True

            x0 = mdp.numx_linalg.solve(-H, f)
            if H_definite_positive and mdp.utils.norm2(x0) <= norm:
                xmin = x0
                # x0 is a minimum
            else:
                xmin = self._maximize(norm, tol, factor=-1)
            if H_definite_negative and mdp.utils.norm2(x0) <= norm :
                xmax= x0
                # x0 is a maximum
            else:
                xmax = self._maximize(norm, tol, factor=None)

        self.xmax, self.xmin = xmax, xmin
        return xmax, xmin

    def _maximize(self, norm, tol = 1.E-4, x0 = None, factor = None):
        H, f = self.H, self.f
        if factor is not None:
            H = factor*H
            f = factor*f
        if x0 is not None:
            x0 = mdp.utils.refcast(x0, self.dtype)
            f = mdp.utils.mult(H, x0)+ f
            # c = 0.5*x0'*H*x0 + f'*x0 + c -> do we need it?
        mu, V = mdp.utils.symeig(H, overwrite=0)
        alpha = mdp.utils.mult(V.T, f).reshape((H.shape[0],))
        # v_i = alpha_i * v_i (alpha is a raw_vector)
        V = V*alpha
        # left bound for lambda
        ll = mu[-1] # eigenvalue's maximum
        # right bound for lambda
        lr = mdp.utils.norm2(f)/norm + ll
        # search by bisection until norm(x)**2 = norm**2
        norm_2 = norm**2
        norm_x_2 = 0
        while abs(norm_x_2-norm_2) > tol and (lr-ll)/lr > epsilon:
            # bisection of the lambda-interval
            lambd = 0.5*(lr-ll)+ll
            # eigenvalues of (lambda*Id - H)^-1
            beta = (lambd-mu)**(-1)
            # solution to the second lagragian equation
            norm_x_2 = (alpha**2*beta**2).sum()
            #%[ll,lr]
            if norm_x_2 > norm_2:
                ll=lambd
            else:
                lr=lambd
        x = (V*beta).sum(axis=1)
        if x0:
            x = x + x0
        return x

    def get_invariances(self, xstar):
        """Compute invariances of the quadratic form at extremum 'xstar'.
        Outputs:

         w  -- w[:,i] is the direction of the i-th invariance 
         nu -- nu[i] second derivative on the sphere in the direction w[:,i]

        IMPORTANT: this method will crash python on 64bit platforms because
        of a bug in numpy.linalg.qr (as of numpy version 1.0.1). This bug
        is fixed in the current numpy subversion repository.
        """
        
        # find a basis for the tangential plane of the sphere in x+
        # e(1) ... e(N) is the canonical basis for R^N
        r = mdp.utils.norm2(xstar)
        P = numx.eye(xstar.shape[0], dtype=xstar.dtype)
        P[:,0] = xstar
        Q, R = numx.linalg.qr(P)
        # the orthogonal subspace
        B = Q[:,1:]
        # restrict the matrix H to the tangential plane
        Ht = mdp.utils.mult(B.T,mdp.utils.mult(self.H,B))
        # compute the invariances
        nu, w = mdp.utils.symeig(Ht)
        nu -= ((mdp.utils.mult(self.H, xstar)*xstar).sum()-(self.f*xstar).sum())/(r*r)
        idx = abs(nu).argsort()
        nu = nu[idx]
        w = w[:,idx]
        w = mdp.utils.mult(B,w)
        return w, nu
        