#
# Hydronic -- calculations for modeling heated structures
#
# Copyright (c) 2006-2026, Perry Kundert
#
# Hydronic is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.  See the LICENSE file at the top of the source tree.
#
# Hydronic is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

"""Fanger's Comfort Equation: Predicted Mean Vote (PMV) and Percentage Dissatisfied (PPD).

All units are SI: temperatures in degrees C, air velocity in m/s, vapour pressure in Pa,
metabolism in met (or W/m^2) and clothing in clo (or m^2K/W).

"""

from __future__ import absolute_import, division, print_function

import math

from .misc import Error, scale


class fanger( object ):
    """Implements Fanger's Basic Comfort Equation.

    A good discussion of its applicability is:

        http://www.nrc-cnrc.gc.ca/obj/irc/doc/pubs/rr/rr162/rr162.pdf,  now:
        https://nrc-publications.canada.ca/eng/view/ft/?id=7525d344-a508-4fdc-9c04-d9d3a9767bdb

    A derivation of this equation is detailed (somewhat incompletely) in:

        http://www.lumasenseinc.com/uploads/News/Articles/English/Technical_Review_No_2-1982_-Thermal_Comfort.pdf, now:
        https://www.bksv.com/media/doc/TechnicalReview1982-2.pdf, "Thermal Comfort", page 3

    The equation depends on humidity, air temperature and velocity, average radiant temperature,
    clothing level and metabolic level.  Metabolic rate is described in either 'met', or raw W/m^2:

    Metabolism, M (met):                                           (W/m^2)
        Activity                                            met     M
        --------                                            ---     -----
        Lying down                                          0.8     47
        Seated quietly                                      1.0     58
        Sedentary activity (office, school)                 1.2     70
        Standing, relaxed                                   1.2     70
        Light activity, standing (shopping, lab, lt. ind.)  1.6     93
        Medium activity, standing (shop asst., dom. work)   2.0    117
        High activity (heavy machine, garage work)          3.0    175
        Running                                             9.0    522

    The insulating (and radiating) value of clothing is expressed in 'clo', or raw m^2K/W:

    Clothing, I_cl (clo):                                         (m^2K/W)
        Clothing Combination                                clo    I_cl
        --------------------                                ---    ------
        Naked                                               0      0
        Shorts                                              0.1    0.016
        Tropical                                            0.3    0.047
        Light Summer (short sleeves, light pants)           0.5    0.078
        Working Clothes (cotton shirt + jeans)              0.8    0.124
        Typical indoor winter (shirt + sweater)             1.0    0.155
        Heavy business suit                                 1.5    0.233

    Fanger's Comfort Equation:

        (M-W)
          - 3.05 x 10^-3 x {5733 - 6.99 x (M-W) - P_a}
          - 0.42 { (M-W) - 58.15 }
          - 1.7 x 10^-5 x M x (5867 - P_a)
          - 0.0014 x M x (34 - t_a)
        = 3.96 x 10^-8 x f_cl { (t_cl + 273.15)^4 - (t_r + 273.15)^4 }
          + C
    where:
        M:     Metabolism, in met (converted to W/m^2)
        W:     External work performed (subtracted from M, usually 0.)
        t_a:   Air temperature (dec. C)
        t_s:   Temperature of skin (deg. C)
        t_s  = 35.7 - 0.028 (M-W)
        E_sw:  Sweat loss (W/m^2)
        E_sw = 0.42 { (M-W) - 58.15 }    #
        E_res= 0.0014 M(34 - t_a)        # Heat loss from respiration

        C:     heat exchange by convection (W/m^2)
        C    = f_cl x h_c x (t_cl - t_a)
        t_cl =
          t_s - 0.155 x clo [
            (M-W)
            - 3.05 x 10^-3 x {5733 - 6.99 x (M-W) - p_a}
            - E_sw
            - 1.7 x 10^-5 x M (5867 - p_a)
            - 0.0014 x M x (34 - t_a) ]

        h_c:  Convective heat transfer (W/M^2 K)
        h_c  = A) 2.38 x (t_cl - t_a) ^ 0.25 # (for A > B); free convection
        h_c  = B) 12.1 x sqrt( v_ar )        # (for A < B); forced convection

        f_cl: Clothing area factor
        f_cl = A) 1.00 + 0.2 x clo      # for clo <= 0.5
        f_cl = B) 1.05 + 0.1 x clo      # for clo >  0.5

    From B. A. McIntyre's Bioengineering, thermal physiology, and comfort, Volume 10, pp.198, there
    are simplifications of the Fanger equations that work within certain constraints:

    For M < 150 W/m^2 (met ~2.5), and I < 0.233 m^2 K/W (clo ~1.5), this simplification
    (for a target effective temperature) yielded error < 0.5K.

        t_sub = 33.5 - 3 x I_cl - (0.08 + 0.05 x I_cl) x M

    and, where t_a and t_r are different, for v < 0.1 m/s:

        t_sub = 0.56 x t_a + 0.44 x t_r

    for v > 0.1 m/s (high air velocity), a much more complex equation:

        t_sub = 0.44 x t_r + (5 - (10 x v)^0.5 x (5 - t_a))/(0.44 + 0.56 x (10 x v)^0.5)

    So for a typical residence, the lower complexity formula will suffice.  Later in
    B. A. McIntyre's Bioengineering book, on pp. 210, he also reveals that once the perceived
    temperature is correct, changes in humidity do little to affect comfort.  In fact, "...a change
    in relative humidity from 20% to 75% would reduce the preferred temperature by 1K."  So, using
    the simplified equation (and ignoring humidity) is probably going to be adequate for an effective
    radiant and air temperature control strategy.


    This simplification might be useful, in concert with an "adaptive model" for thermal neutrality.
    From:

        http://nceub.commoncense.info/uploads/Saberi.pdf

    it appears that the "neutral" temperature (at which a person feels thermally neutral,
    "comfortable") is related to the average outdoor temperature, by the equation:

        t_n = 11.9 + 0.534 x t_m (from Humphreys)
    or:
        t_n = 17.6 + 0.314 x t_m (from Auliciemes)

    where:
        t_n = neutral temp (in C)
        t_m = Mean outdoor temp (in C)

    From the data underlying these equations, it appears that Fanger et.al. computed their comfort
    equation temperatures in an environment where the outdoor temperature was around 25 C.  This
    means that we must adjust the target temperatures using these equations.  If we adjust the
    actual t_a and t_r upward or downward by the difference between the 25 C, and the computed t_n
    for the outdoor temperature, before computing the Fanger L,

    This result is probably due to the fact that humans adjust their food intake and metabolic rate
    upwards when it is cold outside.  This suggests that it might be possible to simply add to the
    metabolic rate input to Fanger's equation, the colder the outside temperature is...

    Further neutral temperature equations from: http://www.eurojournals.com/ejsr_27_2_06.pdf
        t_n_o = 17 + 0.38 x t_o (Humphreys MA, 1976)
        t_n_i = 2.6 + 0.831 x t_i (Orosa JA, 2008)
        t_n_o = 11.9 + 0.534 x t_o (Orosa JA, 2008)
        t_n_i = 5.41 + 0.731 x t_i
        t_n_o = 17.6 + 0.31 x t_o
        t_n_i_o = 9.22 + 0.48 x t_i + 0.14 x t_o
        t_c   = 17.8 + 0.31 x t_o (ASHRAE)
    where:
        t_o = outdoor temperature
        t_i = mean indoor temperature
        t_c = the comfort temperature
        t_n_o = neutral temperature based on mean outdoor temperature
        t_n_i = neutral temperature based on mean indoor temperature

    All these assume near sedentary activity, and freely adaptable clothing.


    Another description of Fanger's equation is from:

        http://ergo.human.cornell.edu/studentdownloads/DEA3500notes/Thermal/thcomnotes2.html

    Fanger's Comfort Equation This equation contains terms which relate to:

    functions of clothing:
        Icl = clothing insulation in clothes
        fcr = ratio of clothed/nude surface area
    functions of activity:
        H = Metabolic heat production (w/m2)
        M = Metabolic free energy production (external work)(w/m2)
    Environmental variables:
        Ta = Air temperature (C)
        Tr = Mean radiant temperature (C)
        v = Relative air speed (m/s)
        Pa = Vapor pressure of water vapor (mb)

    Fanger's Equation
        (hc = convective transfer coefficient w/m2 K)
        H - 0.31(57.4 - 0.07H - Pa) - 0.42(H-58) - 0.0017M(58.7 - Pa) - 0.0014M(34 - Ta) =
        3.9 x 10-8fcl {(Tcl + 273)4 - (Tr + 273)4} + fcl hc (Tcl - Ta)

    Where the clothing surface temperature, Tcl, is given by
        Tcl = 35.7 - 0.0275H + 0.155Iclo {H - 0.31(57.4 - 0.07H - Pa) - 0.42(H - 58) - 0.0017M(58.7 - Pa) - 0.0014M(34 - Ta)}.

    In addition to this, discomfort may occur when the skin is wetted (sweat, water, etc.) and
    Fanger has produced an equation for skin wettedness which can be used as a test to exclude
    conditions which satisfy the comfort equation:

    Predicted Mean Vote (PMV)

    The problem with Fanger's equation is that when people are not satisfied, this is not a measure
    of how uncomfortable deviation is; therefore Fanger developed PMV = mean vote on ASHRAE scale
    (Hot / warm / slightly warm / neutral / slightly cool / cool / cold). PMV can be predicted from
    Fanger's equation thus:

        PMV = 4 + (0.303 exp(-0.036H) + 0.0275) x {6.57 + 0.46H + 0.31Pa + 0.0017HPa + 0.0014HTa - 4.13 fcl (1 + 0.01dT) (Tcl - Tr) - hcfcl (Tcl - Ta)}

    where Tcl (surface temperature of clothed body) =
        35.7 - 0.0275H + 0.155 Iclofcl (4.13 (1 + 0.Old Temp) 1 + 0.155 Iclofcl (4.13 (1 + 0.Old Temp)thc

    where hc = 2.4(Tcl - Ta)0.25 or 12.1 square root of v (air speed) which is greater
    and dT = Tr - 22.


    From the definitive source, the ISO 7730 standard (2005-11-15):

        http://www.ntm.ru/UserFiles/File/document/Microklimat/Norm/ISO_7730_2005.pdf

    (with corrections (re: HL6) from http://www.naun.org/journals/mechanics/17-105.pdf)

        PMV = (0.303 x e^(-0.036 x M) + 0.028) x L

        L   = (M-W)
              - 3.05 x 10^-3 x [5733 - 6.99 x (M-W) - P_a]
              - 0.42 x [(M-W) - 58.15]
              - 1.7 x 10^-5 x M x (5867 - P_a)
              - 1.4 x 10^-3 x M x (34 - t_a)
              - 3.96 x 10^-8 x f_cl x [(t_cl +273)^4 - (t_r + 273)^4]
              - f_cl x h_c x (t_cl - t_a)
        t_cl = 35.7 - 0.028 x (M-W)
              - I_cl
                  x (3.96 x 10^-8 x f_cl
                      x [(t_cl + 273)^4 - (t_r + 273)^4]
                      + f_cl x h_c x (t_cl - t_a)]

        h_c:  Convective heat transfer (W/M^2 K)
        h_c  = A) 2.38 x (t_cl - t_a) ^ 0.25 # (for A > B); free convection
        h_c  = B) 12.1 x sqrt( v_ar )        # (for A < B); forced convection

        f_cl: Clothing area factor
        f_cl = A) 1.00 + 1.290 x I_cl      # for I_cl <= 0.078 m^2K/W
        f_cl = B) 1.05 + 0.645 x I_cl      # for I_cl >  0.078 m^2K/W
    where:
        M is the metabolic rate, in watts per square metre (W/m2);
        W is the effective mechanical power, in watts per square metre (W/m^2);
        I_cl is the clothing insulation, in square metres kelvin per watt (m^2 K/W);
        f_cl is the clothing surface area factor;
        t_a is the air temperature, in degrees Celsius (C);
        t_r is the mean radiant temperature, in degrees Celsius (C);
        v is the relative air velocity, in metres per second (m/s);
        p_a is the water vapour partial pressure, in pascals (Pa);
        h_c is the convective heat transfer coefficient, in watts per square metre kelvin [W/(m^2K)];
        t_cl is the clothing surface temperature, in degrees Celsius (C).
        1 metabolic unit = 1 met = 58.2 W/m2
        1 clothing unit = 1 clo = 0.155 m^2K/W

    PMV should only be used between -2 and 2, and if the 6 main variables are in the ranges:

        M   46 W/m^2  to 232 W/m^2 (0.8 met to 4 met);
        I_cl 0 m^2K/W to 0.310 m^2K/W (0 clo to 2 clo);
        t_a 10 C      to 30 C;
        t_r 10 C      to 40 C;
        v    0 m/s    to 1 m/s;
        p_a  0 Pa     to 2700 Pa.

    A BASIC program implement PMV is provided:
     10 Computer program (BASIC) for calculation of
     20 Predicted Mean Vote (PMV) and Predicted Percentage of Dissatisfied (PPD)
     30 in accordance with International Standard, ISO 7730
     40 CLS: PRINT  "DATA ENTRY" data entry
     50 INPUT " Clothing (clo) "; CLO
     60 INPUT " Metabolic rate (met) " MET
     70 INPUT " External work, normally around 0 (met) " WME
     80 INPUT " Air temperature (C) " TA
     90 INPUT " Mean radiant temperature (C) " TR
    100 INPUT " Relative air velocity (m/s) " VEL
    110 INPUT " ENTER EITHER RH OR WATER VAPOUR PRESSURE BUT NOT BOTH"
    120 INPUT " Relative humidity (%) " RH
    130 INPUT " Water vapour pressure (Pa) " PA
    140 DEF FNPS (T) = EXP (16.6536-4030.183/T+235))  : saturated vapour pressure, kPa
    150 IF PA = 0 THEN PA = RH * 10 * FNPS (TA)       : water vapour pressure, Pa
    160 ICL = .155 * CLO                              : thermal insulation of the clothing in m^2K/W
    170 M = MET * 58.15                               : metabolic rate in W/m2
    180 W = WME * 58.15                               : external work in W/m2
    190 MW = M - W                                    : internal heat production in the human body
    200 IF ICL < .078
        THEN FCL = 1 + 1.29 * ICL
        ELSE FCL = 1.05 + 0.645 * ICL                 : clothing area factor
    210 HCF = 12.1 * SQR (VEL)                        : heat transf. coeff. by forced convection

    220 TAA = TA + 273                                : air temperature in Kelvin
    230 TRA = TR + 273                                : mean radiant temperature in Kelvin
    240 -----CALCULATE SURFACE TEMPERATURE OF CLOTHING BY ITERATION ---
    250 TCLA = TAA + (35.5-TA) / (3.5 * ICL + .1)     : first guess for surface temperature of clothing
    260 P1 = ICL * FCL                                : calculation term
    270 P2 = P1 * 3.96                                : calculation term
    280 P3 = P1 * 100                                 : calculation term
    290 P4 = P1 * TAA                                 : calculation term
    300 P5 = 308.7 - .028 * MW + P2 * (TRA/100) * 4
    310 XN = TLCA / 100
    320 XF = XN
    330 N = 0                                         : N: number of iterations
    340 EPS = .00015                                  : stop criteria in iteration
    350 XF = (XF + XN)/2
    360 HCN =2.38 * ABS (100 * XF - TAA) ^ .25        : heat transf. coeff. by natural convection
    370 IF HCF>HCN THEN HC = HCF ELSE HC = HCN
    380 XN = (P5 + P4 * HC - P2 * XF ^ 4) / (100 + P3 * HC)
    390 N = N + 1
    400 IF N > 150 THEN GOTO 550
    410 IF ABS (XN - XF) > EPS GOTO 350
    420 TCL = 100 * XN - 273                          : surface temperature of the clothing
    430 --------------------------------HEAT LOSS COMPONENTS -----------------------------------
    440 HL1 = 3.05 * .001 (5733-6.99 * MW-PA)         : heat loss diff. through skin
    450 IF MW > 58.15 THEN HL2 = .42 * (MW - 58.15)
        ELSE HL2 = 0!                                 : heat loss by sweating (comfort)
    460 HL3 = 1.7 * .00001 * m * (5867-PA)            : latent respiration heat loss
    470 HL4 = .0014 * m * (34 - TA)                   : dry respiration heat loss
    480 HL5 = 3.96 * FCL * (XN^4 - (TRA/100^4)        : heat loss by radiation
    500 --------------------------------CALCULATE PMV AND PPD -----------------------------------
    510 TS = .303 * EXP (- .036 * m) + .028           : thermal sensation trans coeff
    520 PMV = TS * (MW - HL1 - HL2 - HL3 - HL4 - HL5 - HL6) : predicted mean vote
    530 PPD = 100 - 95 * EXP (- .03353 * PMV ^ 4 - .2179 * PMV^ 2) : predicted percentage dissat.
    540 GOTO 570
    550 PMV = 999999!
    560 PPD = 100
    570 PRINT:PRINT "OUTPUT" : output
    580 PRINT " Predicted Mean Vote  (PMV): "
       :PRINT USING "# # . #": PMV


    From:

        http://listserv.repp.org/pipermail/greenbuilding_listserv.repp.org/2009-April/011178.html (gone, 20261110)

    we have a seemingly corrected version:

    10 CLO = 1'clothing insulation (clo)
    20 MET=1.1'metabolic rate (met)
    30 WME=0'external work (met)
    40 VEL=.1'air velocity
    50 RH=0'relative humidity (%)
    60 DATA 70,69,.008,0.05,1
    70 DATA 69.15,70,.008,0.05,1
    80 FOR CASE = 1 TO 2
    90 READ TAF,TRF,WA,VEL,CLO
    100 TA=(TAF-32)/1.8'air temp (C)
    110 TR=(TRF-32)/1.8'mean radiant temp (C)
    120 PA=29.921*3377.2/(1+.62198/WA)'water vapor ressure (Pa)
    130 DEF FNPS(T)=EXP(16.6536-4030.183/(TA+235))'sat vapor pressure, kPa
    140 IF PA=0 THEN PA=RH*10*FNPS(TA)'water vapor pressure, Pa
    150 ICL=.155*CLO'clothing resistance (m^2K/W)
    160 M=MET*58.15'metabolic rate (W/m^2)
    170 W=WME*58.15'external work in (W/m^2)
    180 MW=M-W'internal heat production
    190 IF ICL<.078 THEN FCL=1+1.29*ICL ELSE FCL=1.05+.645*ICL'clothing
    factor
    200 HCF=12.1*SQR(VEL)'forced convection conductance
    210 TAA=TA+273'air temp (K)
    220 TRA=TR+273'mean radiant temp (K)
    230 TCLA=TAA+(35.5-TA)/(3.5*(6.45*ICL+.1))'est clothing temp
    240 P1=ICL*FCL:P2=P1*3.96:P3=P1*100:P4=P1*TAA'intermediate values
    250 P5=308.7-.028*MW+P2*(TRA/100)^4
    260 XN=TCLA/100
    270 XF=XN
    280 N=0'number of iterations
    290 EPS=.00015'stop iteration when met
    300 XF=(XF+XN)/2'natural convection conductance
    310 HCN=2.38*ABS(100*XF-TAA)^.25
    320 IF HCF>HCN THEN HC=HCF ELSE HC=HCN
    330 XN=(P5+P4*HC-P2*XF^4)/(100+P3*HC)
    340 N=N+1
    350 IF N>150 GOTO 470
    360 IF ABS(XN-XF)>EPS GOTO 300
    370 TCL=100*XN-273'clothing surface temp (C)
    380 HL1=.00305*(5733-6.99*MW-PA)'heat loss diff through skin
    390 IF MW>58.15 THEN HL2=.42*(MW-58.15) ELSE HL2=0'heat loss by sweating
    400 HL3=.000017*M*(5867-PA)'latent respiration heat loss
    410 HL4=.0014*M*(34-TA)'dry respiration heat loss
    420 HL5=3.96*FCL*(XN^4-(TRA/100)^4)'heat loss by radiation
    430 HL6=FCL*HC*(TCL-TA)'heat loss by convection
    440 TS=.303*EXP(-.036*M)+.028'thermal sensation transfer coefficient
    450 PMV=TS*(MW-HL1-HL2-HL3-HL4-HL5-HL6)'predicted mean vote
    460 GOTO 480
    470 PMV=99999!:PPD=100
    480 PRINT TAF,TRF,PMV
    490 NEXT CASE
    500 LIST 70


    From Truong (2010): http://hdl.handle.net/1721.1/61509, we get the following updates to Fanger's
    equations, especially focussed on better predicting comfort in Naturally Ventilated (NV)
    buildings:

    Fanger underestimated the increase in clothing surface area, leading to too high
    comfort temperatures with higher clo values (for all building types):

    f_cl = 1 + 0.30 * clo

    """
    MET                         = 58.0          # W/m^2 per met (ISO 7730 uses 58.15 or 58.2)
    CLO                         = 0.155         # m^2K/W per clo

    def __init__( self, met=None, M=None, clo=None, I_cl=None, v=0.0,
                  t_a=None, t_r=None, hum=None, P_w=None, W=0.0, mit=True ):
        """Defaults are sedentary activity or standing (met 1.2), working clothes (clo 0.8), no air
        velocity, no net work output.  Optional arguments remembered are:

        met/M           Metabolic rate in either met or M (W/m^2); both not allowed
        clo/I_cl        Clothing in either clo or I_cl (m^2 K/W) ; both not allowed
        v               Air velocity, in m/s
        t_a, t_r        Air and average radiant temperatures (degrees C)
        hum/P_w         Relative humidity (0,1), or vapour pressure of water in ambient air (Pa)
        W               External work performed (W/m^2), usually 0.
        mit             Use Truong (2010)'s revised clothing area factor f_cl

        If you specify humidity in terms of relative humidity (hum, domain (0.0,1.0)), the vapour
        pressure is computed from the air temperature t_a in effect at the time of each computation.

        """
        if met is not None and M is not None:
            raise Error( "Specify metabolism as met or M, not both" )
        if clo is not None and I_cl is not None:
            raise Error( "Specify clothing as clo or I_cl, not both" )
        if hum is not None and P_w is not None:
            raise Error( "Specify humidity as hum or P_w, not both" )
        self._M                 = None
        self._M                 = self.M( met=1.2 if met is None and M is None else met, M=M )
        self._I_cl              = None
        self._I_cl              = self.I_cl( clo=0.8 if clo is None and I_cl is None else clo, I_cl=I_cl )
        self.v                  = v
        self.t_a                = t_a
        self.t_r                = t_r
        self.hum                = hum
        self._P_w               = P_w
        if hum is not None and t_a is not None:
            self._P_w           = self.P_w( t_a=t_a, hum=hum )
        self.W                  = W
        self.mit                = mit
        self._t_cl              = None

    def metabolism( self, rate=None ):
        """Returns (rate, met, "description") of the current metabolic rate.  Optionally, set the 'rate',
        using a value in the domain [0,1] --> (0.8,3.0) met.

        """
        if rate is None:
            M                   = self.M()
        else:
            M                   = self._M = self.M( met=scale( rate, (0., 1.), (0.8, 3.0) ))
        if M is None:
            return ( float( 'nan' ), float( 'nan' ), "unknown" )
        met                     = M / self.MET
        if rate is None:
            rate                = scale( met, (0.8, 3.0), (0., 1.) )

        for lim, desc in ( ( ( 0.8 + 1.0 ) / 2, "lying" ),
                           ( ( 1.0 + 1.2 ) / 2, "sitting" ),
                           ( ( 1.2 + 1.6 ) / 2, "standing" ),
                           ( ( 1.6 + 2.0 ) / 2, "light" ),
                           ( ( 2.0 + 3.0 ) / 2, "medium" ),
                           ( ( 3.0 + 4.0 ) / 2, "hard" )):
            if met < lim:
                return ( rate, met, desc )
        return ( rate, met, "heavy" )

    def M( self, met=None, M=None ):
        """Support specifying M as either met or M, or from precomputed _M attribute"""
        if met is not None:
            if not 0.0 <= met <= 9.0:
                raise Error( "Metabolism %r met outside (0,9)" % ( met, ))
            return met * self.MET
        if M is not None:
            return M
        return self._M

    def clothing( self, amount=None ):
        """Returns (amount, clo, "description"), where amount is in the range [0,1] --> (0,3) clo.  1.0
        clo is defined as the amount of clothes required for an average person to be indefinitely
        comfortable at 20C, 50%RH, 0m/s.  4.0 is the maximum possible amount of clothing; basically
        "Eskimo" clothing; full furs.  Optionally pass amount to adjust clothing level.

        """
        if amount is None:
            I_cl                = self.I_cl()
        else:
            I_cl                = self._I_cl = self.I_cl( clo=scale( amount, (0., 1.), (0., 3.) ))
        if I_cl is None:
            return ( float( 'nan' ), float( 'nan' ), "unknown" )
        clo                     = I_cl / self.CLO
        if amount is None:
            amount              = scale( clo, (0., 3.), (0., 1.) )

        for lim, desc in ( ( ( 0.0 + 0.1 ) / 2, "naked" ),
                           ( ( 0.1 + 0.3 ) / 2, "shorts" ),
                           ( ( 0.3 + 0.5 ) / 2, "tropical" ),
                           ( ( 0.5 + 0.8 ) / 2, "summer" ),
                           ( ( 0.8 + 1.0 ) / 2, "casual" ),
                           ( ( 1.0 + 1.5 ) / 2, "indoor" ),
                           ( ( 1.5 + 2.0 ) / 2, "winter" ),
                           ( ( 2.0 + 3.0 ) / 2, "heavy" )):
            if clo < lim:
                return ( amount, clo, desc )
        return ( amount, clo, "blankets" )

    def I_cl( self, clo=None, I_cl=None ):
        """Support specifying I_cl either directly or from clo, or from a precomputed self._I_cl."""
        if clo is not None:
            if not 0.0 <= clo <= 3.0:
                raise Error( "Clothing %r clo outside (0,3)" % ( clo, ))
            return clo * self.CLO
        if I_cl is not None:
            return I_cl
        return self._I_cl

    def f_cl( self, I_cl ):
        """The clothing area factor.  The updated f_cl = 1 + 0.3 x clo equation is used, if 'mit' mode is
        true.

        """
        if self.mit:
            return 1.00 + 0.3 * I_cl / self.CLO
        if I_cl < 0.078:
            return 1.00 + 0.2 * I_cl / self.CLO
        return 1.05 + 0.1 * I_cl / self.CLO

    def t_cl_h_c( self, M, W, I_cl, f_cl, v, t_a, t_r, error=1e-6, allow=1e-4,
                  reps=150, advance=5 ):
        """Produce an refined estimate of t_cl and h_c to within 'err' of 1e-4.  Since this algorithm
        deals in 1/100th Kelvins, the error will be amplified by 100 in the result, so we should try
        to solve to 1e-6.  This should avoid getting too close to the limits of the underlying
        floating point format, and usually take around 10 iterations.  However, degenerate cases in
        prior implementations have been observed; for example, the loop oscillates between two
        values, never approaching closer than an error of 0.00000614 after 37 iterations, settling
        into an oscillation between two values:

            t_cl ( 37): 2.91945054 (err 0.00000614)
            t_cl ( 74): 2.91944133 (err 0.00000614)
            t_cl (111): 2.91945054 (err 0.00000614)
            ...
            t_cl (141): 2.91945054 (err 0.00000614)
            ...
            t_cl (146): 2.91944133 (err 0.00000614)
            t_cl (147): 2.91945054 (err 0.00000614)
            t_cl (148): 2.91944133 (err 0.00000614)
            t_cl (149): 2.91945054 (err 0.00000614)

            'xn': 2.9194505366000816,
            'xf': 2.919444401018496,
            'taa': 291.94444544017557,
            'I_cl': 0.46499999999999997,
            't_a': 18.79444544017561,
            'hcf': 0.0,
            't_r': 14.251083402047804,
            'hcn': 0.11440058061771223,
            'f_cl': 1.9,
            'M': 46.400000000000006,
            'reps': 150,
            'W': 0.0,
            'hc': 0.11440058061771223,
            'p2': 3.4986599999999997,
            'p3': 88.35,
            'p1': 0.8835,
            'p4': 257.9329175463951,
            'err': 1e-07,
            'p5': 546.1024074023035,
            'tra': 287.4010834020478,
            'n': 149,
            'mw': 46.400000000000006,
            'v': 0.0

        Or, worse yet, not even within 1e-6:
            'xf': 2.9814100885428747,
            't_a': 24.989128226382643,
            't_r': 22.458774905050937,

        Instead of a fixed number of iterations, we'll simply iterate 'til we cease advancing the
        convergence, or we hit our goal 'error' limit, and only failing if we hit our ultimate rep
        limit, or cease converging without getting within our maximum 'allow' error limit...

        Uses the self._t_cl as the last estimate, assuming that subsequent calls will change input
        terms only slightly.  Pretty much straight from the ISO 7730 BASIC program.

        """
        mw                      = M - W
        hcf                     = 12.1 * math.sqrt( v )
        taa                     = t_a + 273.15          # Air temp, K
        tra                     = t_r + 273.15          # Radiant temp, K
        p1                      = I_cl * f_cl
        p2                      = p1 * 3.96
        p3                      = p1 * 100
        p4                      = p1 * taa
        p5                      = 308.7 - .028 * mw + p2 * math.pow( tra / 100, 4 )
        if self._t_cl is None:
            self._t_cl          = t_a + ( 35.5 - t_a ) / ( 3.5 * ( 6.45 * I_cl + .1 ))
        xf = xn                 = ( self._t_cl + 273.15 ) / 100

        converged               = False
        n                       = 0
        least                   = {}
        while not converged:
            xf                  = ( xf + xn ) / 2
            hcn                 = 2.38 * math.pow( abs( 100 * xf - taa ), .25 )
            hc                  = max( hcf, hcn )
            xn                  = ( p5 + p4 * hc - p2 * math.pow( xf, 4 )) / ( 100 + p3 * hc )
            diff                = abs( xf - xn )
            converged           = n > 5 and diff <= error * abs( xn )
            n                  += 1
            if not least or diff < least['diff']:
                least['n']      = n
                least['diff']   = diff
                least['xn']     = xn
            if n > least['n'] + advance or n > reps:
                break

        if not converged and diff > allow:
            # Well, we didn't converge xf/xn within 'error'; if we didn't even get within
            # 'allow', we'll have to raise an exception.
            raise Error( "Couldn't refine t_cl to within %g, in %d iterations: locals:\n%r" % (
                allow, n, locals() ))

        self._t_cl              = ( 100 * least['xn'] ) - 273.15
        return self._t_cl, hc

    def t_d( self, e ):
        """Return dewpoint temperature (degrees C), from vapour pressure e (in Pa).  Equation is for
        millibars (mb), which are Pa/100.  See:

            http://facstaff.unca.edu/cgodfrey/courses/advcomp/cgi.shtml

        """
        e_ln                    = math.log( e / 100. / 6.112 )
        return ( 243.5 * e_ln ) / ( 17.67 - e_ln )

    def p_sat( self, t_a ):
        """Saturated Vapour Pressure, in Pa, for a given air temperature t_a.  From ISO 7730 BASIC
        program, and:

            http://www.dtic.mil/cgi-bin/GetTRDoc?AD=ADA305730

        """
        return math.exp( 16.6536 - ( 4030.183 / ( t_a + 235. ))) * 1000.

    def P_w( self, t_a=None, hum=None, P_w=None ):
        """Compute actual vapour pressure P_w in Pascals (Pa), from Relative Humidity (hum, ~(0., 1.)),
        and air temperature t_a (C).  If neither hum nor P_w is supplied, returns the precomputed
        self._P_w.

            RH: Relative Humidity
            RH     = e / e_s
        or:
            e      = RH x e_s (in mb)
            P_w    = e x 100. (in Pa)
        where:
            P_w:    Vapour pressure (Pa)
            e:      Vapour pressure (millibars, mb)

            e_s(t_a): Saturation Vapour Pressure (mb), from air temperature (degress C)
            (From: http://facstaff.unca.edu/cgodfrey/courses/advcomp/cgi.shtml; WRONG)
            e_s(t_a) = 6.112 x 10^((17.67 x t_a) / (t_a + 243.5))
        or:
            (From: http://www.theweathernetwork.com/glossary/humidex)
            e_s(t_a) = 6.112 x 10^(7.5 x t_a/(237.7 + T))
            1 Bar  = 100,000 Pa
            1 mb   = 100 Pa

        We use the ISO 7730 BASIC program's saturation vapour pressure; see p_sat.
        """
        if P_w is not None:
            return P_w
        if hum is not None:
            # No P_w, but we have RH%; compute vapour pressure (Pa) using air temperature (C)
            if t_a is None or not -100. < t_a < 100.:
                raise Error( "Relative humidity requires an air temperature in (-100,100) C; not %r" % (
                    t_a, ))
            if not 0.0 <= hum <= 1.0:
                raise Error( "Relative humidity %r outside (0,1)" % ( hum, ))
            return hum * self.p_sat( t_a=t_a )
        return self._P_w

    def L( self, met=None, M=None, clo=None, I_cl=None, v=None,
           t_a=None, t_r=None, hum=None, P_w=None, W=None ):
        """Fanger's Comfort Equation.  Computes the net (+/-) thermal load (L) on a typical human body,
        subject to the specified parameters, and returns it scaled to the Predicted Mean Vote (PMV)
        thermal sensation scale (see PMV).  Any terms not defined must have been specified at the
        time of object creation, or result will be an exception.

        """
        # Metabolism, clothing
        M                       = self.M( met=met, M=M )
        I_cl                    = self.I_cl( clo=clo, I_cl=I_cl )
        f_cl                    = self.f_cl( I_cl=I_cl )

        # External Work
        W                       = W if W is not None else self.W

        # Environmental conditions.  A relative humidity (if specified) tracks the air temperature.
        v                       = v if v is not None else self.v
        t_a                     = t_a if t_a is not None else self.t_a
        t_r                     = t_r if t_r is not None else self.t_r
        if t_a is None or t_r is None:
            raise Error( "Fanger's equation requires air and radiant temperatures t_a and t_r" )
        P_w                     = self.P_w( t_a=t_a, hum=hum if hum is not None or P_w is not None else self.hum,
                                            P_w=P_w )
        if P_w is None:
            raise Error( "Fanger's equation requires humidity hum or vapour pressure P_w" )

        # Compute clothing temperature t_cl, iteratively, since the formula itself depends on
        # t_cl. We'll iterate 'til the computed t_cl is within ~10^-4 of the last sample, and save
        # the last computed value in self._t_cl (for the next time).
        t_cl, h_c               = self.t_cl_h_c( M=M, W=W, I_cl=I_cl, f_cl=f_cl, v=v, t_a=t_a, t_r=t_r )

        # Compute all heat losses (W/m^2)
        hl1                     = .00305 * ( 5733 - 6.99 * ( M - W ) - P_w )    # Through skin
        hl2                     = max( 0.42 * ( ( M - W ) - 58.15 ), 0. )       # From sweating
        hl3                     = .000017 * M * ( 5867 - P_w )                  # Latent respiration
        hl4                     = .0014 * M * ( 34 - t_a )                      # Dry respiration
        hl5                     = 3.96 * f_cl * ( math.pow( ( t_cl + 273.15 ) / 100, 4 )  # Radiation
                                                  - math.pow( ( t_r + 273.15 ) / 100, 4 ))
        hl6                     = f_cl * h_c * ( t_cl - t_a )                   # Convection
        balance                 = ( M - W ) - hl1 - hl2 - hl3 - hl4 - hl5 - hl6
        ts                      = .303 * math.exp( -.036 * M ) + .028         # Thermal sensation coefficient
        return ts * balance

    def L_simple( self, met=None, M=None, clo=None, I_cl=None, v=None,
                  t_a=None, t_r=None, hum=None, P_w=None, W=None ):
        """A simplified thermal loading calculation, that operates using an estimate of perceived
        temperatures.  It simply returns the difference between desired and perceived temperatures,
        for different levels of clothing and metabolic rate.  Result is in degrees C difference
        between perceived and desired temperatures.  Humidity and external work are ignored.

        """
        M                       = self.M( met=met, M=M )
        I_cl                    = self.I_cl( clo=clo, I_cl=I_cl )
        v                       = v if v is not None else self.v
        t_a                     = t_a if t_a is not None else self.t_a
        t_r                     = t_r if t_r is not None else self.t_r
        desired, perceived      = self.t_sub( M=M, I_cl=I_cl, t_a=t_a, t_r=t_r, v=v )
        return perceived - desired

    def t_sub( self, M, I_cl, t_a, t_r, v ):
        """McIntyre's simplified desired and perceived temperatures (C); see class docstring."""
        t_sub_desired           = 33.5 - 3 * I_cl - ( 0.08 + 0.05 * I_cl ) * M
        if v > 0.1:
            t_sub_perceived     = 0.44 * t_r + ( 5. - math.pow( 10 * v, 0.5 ) * ( 5. - t_a )) / (
                0.44 + 0.56 * math.pow( 10 * v, 0.5 ))
        else:
            t_sub_perceived     = 0.56 * t_a + 0.44 * t_r
        return t_sub_desired, t_sub_perceived

    def PMV( self, **kwargs ):
        """Compute Predicted Mean Vote on the ASHRAE thermal sensation scale (-3.,+3):

            +3 hot
            +2 warm
            +1 slightly warm
             0 neutral
            -1 slightly cool
            -2 cool
            -3 cold

            PMV  = (0.303 x e^(-0.036 x M) + 0.028) x L
        where:
            M: Metabolic rate (W/m^2)
            L: thermal load; difference between internal heat production and heat lost to environment

        This is exactly what L() computes (and has always returned), so PMV is an alias for L,
        accepting all the same keyword args.

        """
        return self.L( **kwargs )

    def PPD( self, pmv=None, **kwargs ):
        """Predicted Percentage of Dissatisfied (5% to 100%), from the PMV (ISO 7730, eq. 4):

            PPD = 100 - 95 x e^(-0.03353 x PMV^4 - 0.2179 x PMV^2)

        Even at a neutral PMV of 0, 5% of people are dissatisfied; at PMV +/-0.5, ~10%.  Supply a
        precomputed 'pmv', or the same keyword args as PMV.
        """
        if pmv is None:
            pmv                 = self.PMV( **kwargs )
        return 100 - 95 * math.exp( -0.03353 * pmv ** 4 - 0.2179 * pmv ** 2 )

    def setpoint( self, pmv=0.0, lo=0.0, hi=40.0, error=1e-3, **kwargs ):
        """Air temperature t_a (C) within (lo,hi) yielding the target 'pmv' (default: neutral), given
        all other conditions (eg. the mean radiant temperature t_r).  This is the air temperature a
        comfort-seeking thermostat should target.  PMV rises monotonically with t_a, so bisect.

        """
        if 't_a' in kwargs:
            raise Error( "setpoint computes t_a; do not specify it" )
        pmv_lo, pmv_hi          = self.PMV( t_a=lo, **kwargs ), self.PMV( t_a=hi, **kwargs )
        if not pmv_lo <= pmv <= pmv_hi:
            raise Error( "PMV %+.2f not attainable in t_a (%g,%g)C; PMV ranges (%+.2f,%+.2f)" % (
                pmv, lo, hi, pmv_lo, pmv_hi ))
        while hi - lo > error:
            mid                 = ( lo + hi ) / 2
            if self.PMV( t_a=mid, **kwargs ) < pmv:
                lo              = mid
            else:
                hi              = mid
        return ( lo + hi ) / 2

    def feels( self, **kwargs ):
        """A description of the PMV: cold, cool, coolish, ok, warmish, warm or hot"""
        pmv                     = self.PMV( **kwargs )
        for lim, desc in ( ( -3, "cold" ), ( -2, "cool" ), ( -1, "coolish" )):
            if pmv <= lim:
                return desc
        for lim, desc in ( ( +3, "hot" ), ( +2, "warm" ), ( +1, "warmish" )):
            if pmv >= lim:
                return desc
        return "ok"
