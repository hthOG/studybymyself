# Synthetic source for a bounded authoring test

This is a fabricated two-page source S2, created for workflow testing. The page and equation numbers below belong only to S2; they are not pages of a real textbook. There are no images and no advanced supplementary derivations. The table is a source table.

## S2 printed page 201 — 7.1 Heat conduction through a slab

We want to determine the rate at which heat is conducted through a flat slab held between two fixed face temperatures. The slab has thickness L and constant cross-sectional area A. Let x increase from the hot face at x=0 to the cold face at x=L. The model assumes one-dimensional steady conduction, constant positive thermal conductivity k, no internal heat generation, and negligible heat loss from the sides. Its two boundaries are T(0)=T_H and T(L)=T_C, with T_H>T_C.

The heat flux q_x is the rate of heat transfer per unit area, in W m^-2, positive in the +x direction. Thermal conductivity k has units W m^-1 K^-1. Fourier's law is an empirical constitutive relation:

q_x = -k dT/dx. (7.1)

The minus sign makes heat flow from higher temperature toward lower temperature. In this model the temperature falls with x, so dT/dx is negative and q_x is positive. The total heat-transfer rate through the area is dot Q=A q_x, in W; flux and total rate are different quantities.

Steady energy conservation, with no generation and constant area, gives dq_x/dx=0. Combining this with constant k gives d^2T/dx^2=0. Integrating and applying both boundary temperatures gives

T(x)=T_H+(T_C-T_H)x/L. (7.2)

Therefore q_x=k(T_H-T_C)/L and dot Q=k A (T_H-T_C)/L. (7.3)

The source omits the algebra determining the two integration constants. These conclusions apply to the stated one-dimensional steady, constant-k model; with internal generation or variable k the preceding derivation cannot be used unchanged. At fixed k, area and temperature difference, doubling L halves the rate. Increasing area increases total rate without changing the flux for the same gradient. If both face temperatures coincide, the profile is constant and the flux is zero. This source does not give a microscopic explanation or discuss transient heat capacity, contact resistance, radiation or convection.

## S2 printed page 202 — Example 7.1, Table 7.1 and Problem 7.1

Example 7.1: A slab with L=0.020 m, A=0.50 m^2 and k=0.80 W m^-1 K^-1 has face temperatures 30 degrees C and 20 degrees C. Calculate (a) the heat flux and its direction and (b) the total heat-transfer rate. The model of page 201 applies. The source solves by finding the linear temperature gradient from the two boundaries, using Fourier's law for the flux, then multiplying by A. Its reported results are q_x=400 W m^-2 in the +x direction and dot Q=200 W.

Table 7.1: Temperature in the slab of Example 7.1

| x / m | T / degrees C |
|---|---|
| 0.000 | 30 |
| 0.010 | 25 |
| 0.020 | 20 |

The table illustrates the linear profile of (7.2). These are calculated model values, not measured experimental data.

Problem 7.1: Keep the conductivity, area and face temperatures of Example 7.1 fixed, but double the thickness to 0.040 m. Find (a) the new heat flux, (b) the total heat-transfer rate and (c) the ratio of the new total rate to Example 7.1. Explain why the flux and total rate have different units. No reference answer is included in S2.
