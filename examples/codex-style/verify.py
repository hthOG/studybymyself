#!/usr/bin/env python3
"""Recompute the synthetic lesson; reject plausible but incorrect candidates.

No textbook provenance or human-review pass is manufactured by this script.
"""
import unittest

import sympy as s


class RindlerChecks(unittest.TestCase):
    def setUp(self):
        self.rho, self.eta, self.sigma = s.symbols("rho eta sigma", positive=True)

    def test_metric_from_jacobian(self):
        rho, eta = self.rho, self.eta
        transform = s.Matrix([rho*s.sinh(eta), rho*s.cosh(eta)])
        jacobian = transform.jacobian([rho, eta])
        metric = s.simplify(jacobian.T * s.diag(-1, 1) * jacobian)
        self.assertEqual(metric, s.diag(1, -rho**2))

    def test_proper_time_and_acceleration(self):
        rho, sigma = self.rho, self.sigma
        worldline = s.Matrix([rho*s.sinh(sigma/rho), rho*s.cosh(sigma/rho)])
        velocity = worldline.diff(sigma)
        acceleration = velocity.diff(sigma)
        minkowski = s.diag(-1, 1)
        self.assertEqual(s.simplify((velocity.T*minkowski*velocity)[0]), -1)
        self.assertEqual(s.simplify((velocity.T*minkowski*acceleration)[0]), 0)
        self.assertEqual(s.simplify((acceleration.T*minkowski*acceleration)[0]), rho**-2)
        self.assertEqual(s.simplify(worldline.subs(sigma, rho*self.eta)),
                         s.Matrix([rho*s.sinh(self.eta), rho*s.cosh(self.eta)]))

    def test_exercise_integrals(self):
        rho, eta = self.rho, self.eta
        first = s.integrate(rho, (eta, 0, 2))
        second = s.integrate(2*rho, (eta, 0, 2))
        self.assertEqual(first, 2*rho)
        self.assertEqual(second, 4*rho)
        self.assertEqual(s.simplify(second/first), 2)
        self.assertEqual(s.simplify((1/(2*rho))/(1/rho)), s.Rational(1, 2))

    def test_reject_missing_square_in_metric(self):
        # Dimensionally wrong candidate; a numerical spot at rho=1 would miss it.
        residual = s.simplify(-self.rho**2 - (-self.rho))
        self.assertNotEqual(residual, 0)
        self.assertEqual(residual.subs(self.rho, 1), 0)
        self.assertNotEqual(residual.subs(self.rho, 2), 0)

    def test_reject_coordinate_time_as_proper_time(self):
        rho, eta = self.rho, self.eta
        position = s.Matrix([rho*s.sinh(eta), rho*s.cosh(eta)])
        wrong_velocity = position.diff(eta)
        norm = s.simplify((wrong_velocity.T*s.diag(-1, 1)*wrong_velocity)[0])
        self.assertEqual(norm, -rho**2)
        self.assertNotEqual(norm, -1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
