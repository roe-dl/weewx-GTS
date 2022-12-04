#!/usr/bin/python3

import math
import sys

"""
  https://de.wikibooks.org/wiki/Tabellensammlung_Chemie/_Stoffdaten_Wasser#Sättigungsdampfdruck
  https://ing-moehn.de/das-ingenieurbuero-stellt-sich-vor/sonstiges/formelsammlung/drei-formeln/
  https://de.wikipedia.org/wiki/Clausius-Clapeyron-Gleichung
  https://de.wikipedia.org/wiki/Sättigungsdampfdruck#Korrekturfaktoren_für_feuchte_Luft
  https://de.wikipedia.org/wiki/Eigenschaften_des_Wassers
  https://de.wikipedia.org/wiki/Vienna_Standard_Mean_Ocean_Water

  "When adhering strictly to the two-point definition for calibration, the 
  boiling point of VSMOW under one standard atmosphere of pressure was 
  actually 373.1339 K (99.9839 °C). When calibrated to ITS-90 (a calibration 
  standard comprising many definition points and commonly used for 
  high-precision instrumentation), the boiling point of VSMOW was slightly 
  less, about 99.974 °C."
  [https://en.wikipedia.org/wiki/Celsius]
 
  Siedepunkt des Wassers nach IPTS-68(?): 99,9839°C bei 1013.25 hPa
  Siedepunkt des Wassers nach ITS-90: 99.9743°C bei 1013.25hPa
  Siedepunkt des Wassers nach IPTS-68: 100°C bei 1013.25hPa ("ocean water")
  Tripelpunkt des Wassers: 0,01°C bei 6.11657hPa

  https://www.uni-frankfurt.de/45359621/Generic_45359621.pdf
  Absolutes Luftdruckmaximum: 1057.8 hPa 23.01.1907 in Berlin
  Absolutes Luftdruckminimum:  948,6 hPa 26.02.1989 in Osnabrück
  
"""

def svpGoffGratch(temp):
    """ Sättigungsdampfdruck nach Goff-Gratch """
    T = temp+273.15
    return math.exp(
           -6094.4642/T
           +21.1249952
           -2.7245552e-2*T
           +1.6853396e-5*T*T
           +2.4575506*math.log(T))*0.01

def svpMagnus(T):
    # https://ing-moehn.de/die-magnus-formel/
    return 6.11657*math.exp(17.5043*T/(241.2+T))

def svpVDI(T):
    # VDI/VDE3514
    # https://ing-moehn.de/das-ingenieurbuero-stellt-sich-vor/sonstiges/formelsammlung/drei-formeln/
    T = T+273.15
    r = T/273.16-1
    return 6.11657*math.exp(273.16/T*(20.10711*r-1.59013*pow(r,1.5)))

    
Exp = math.exp
Power = pow

algorithms=('vaDavisVp','vaBuck','vaBuck81','vaBolton','vaTetenNWS','vaTetenMurray','vaTeten')

# from weewx/uwxutils.py
def SaturationVaporPressure(tempC, algorithm='vaBolton'):
        # comparison of vapor pressure algorithms
        # http://cires.colorado.edu/~voemel/vp.html   
        # (for DavisVP) http://www.exploratorium.edu/weather/dewpoint.html
        if algorithm == 'vaDavisVp':
            # Davis Calculations Doc
            Result = 6.112 * Exp((17.62 * tempC)/(243.12 + tempC))
        elif algorithm == 'vaBuck':
            # Buck(1996)
            Result = 6.1121 * Exp((18.678 - (tempC/234.5)) * tempC / (257.14 + tempC))
        elif algorithm == 'vaBuck81':
            # Buck(1981)
            Result = 6.1121 * Exp((17.502 * tempC)/(240.97 + tempC))
        elif algorithm == 'vaBolton':
            # Bolton(1980)
            Result = 6.112 * Exp(17.67 * tempC / (tempC + 243.5))
        elif algorithm == 'vaTetenNWS':
            #  Magnus Teten
            # www.srh.weather.gov/elp/wxcalc/formulas/vaporPressure.html
            Result = 6.112 * Power(10,(7.5 * tempC / (tempC + 237.7)))
        elif algorithm == 'vaTetenMurray':
            # Magnus Teten (Murray 1967)
            Result = Power(10, (7.5 * tempC / (237.5 + tempC)) + 0.7858)
        elif algorithm == 'vaTeten':
            # Magnus Teten
            # www.vivoscuola.it/US/RSIGPP3202/umidita/attivita/relhumONA.htm
            Result = 6.1078 * Power(10, (7.5 * tempC / (tempC + 237.3)))
        else:
            raise ValueError("Unknown SaturationVaporPressure algorithm '%s'" %
                             algorithm)
        return Result

def boilinglimitsGG(pressure, temp0=100.0, temp1=100.0):
    while True:
        p0 = svpGoffGratch(temp0)
        if pressure>p0: break
        temp0 -= 1.0
    while True:
        p1 = svpGoffGratch(temp1)
        if pressure<p1: break
        temp1 += 1.0
    return temp0,temp1
    
def boilingGG(pressure, eps=0.0001, temp0=85.0, temp1=105.0, log=False, n=0):
    """ Siedetemperatur von Wasser
    """
    t2 = (temp0+temp1)/2
    p2 = svpGoffGratch(t2)
    if log:
        print("%2d %9.5f %9.4f %9.5f %9.5f" % (n,t2,p2,temp0,temp1))
    if abs(pressure-p2)<eps: return t2
    if n>20: return None
    if pressure>p2:
        temp0 = t2
    else:
        temp1 = t2
    return boilingGG(pressure, eps, temp0, temp1, log=log, n=n+1)


def vaporizationEnthalpy(temp):
    """ Verdampfungsenthalpie von Wasser
    
        https://www.biancahoegel.de/thermodynamik/verdampfungsenthalpie.html
        https://de.wikipedia.org/wiki/Verdampfungsenthalpie
        
        Die Gleichung liefert weder für 99.9743°C noch für 100.0°C den
        Wert 40.657 kJ/mol, den man in den Tabellen findet.
    """
    T = (temp+273.15)/1000.0
    return (50.09-0.9298*T-65.19*T*T)*1000.0


def boilingTemperatureCC(pressure, temp1=99.9743, deltaH=40.657):
    """ Siedetemperatur von Wasser
    
        https://de.wikipedia.org/wiki/Clausius-Clapeyron-Gleichung
        
        Clausius-Clapeyron-Gleichung, integriert für deltaH=konst.
        
        Gleichung gilt unter der Annahme einer konstanten Verdampfungs-
        enthalpie, was für kleine Temperaturbereiche zutrifft
        
        ln(p2/p1) = H/R * (1/T1 - 1/T2)
    """
    p1 = 1013.25 # hPa           Normaldruck
    T1 = temp1+273.15 # K        Siedetemperatur bei Normaldruck
    deltaH *= 1000.0 # J/mol     molare Verdampfungsenthalpie bei 100°C
    R = 8.314462 # J mol^-1 K^-1 universelle Gaskonstante
    temp = 1.0/(1.0/T1 - math.log(pressure/p1)*R/deltaH)-273.15
    return temp


def svp(temp):
    """ Sättigungsdampfdruck """
    rtn = dict()
    x = svpGoffGratch(temp)
    rtn['Goff-Gratch'] = x
    rtn['Magnus'] = svpMagnus(temp)
    rtn['VDI/VDE3514'] = svpVDI(temp)
    for algorithm in algorithms:
        rtn[algorithm] = SaturationVaporPressure(temp,algorithm)
    return rtn

if len(sys.argv)>1:

    val = float(sys.argv[1])

    if val>200:
    
        # Siedetemperatur in Abhängigkeit vom Druck
        t0,t1 = boilinglimitsGG(val)
        print('Goff-Gratch        %.2f mbar --> %.2f°C' % (val,boilingGG(val,0.01,t0,t1,log=True)))
        print('Clausius-Clapeyron %.2f mbar --> %.2f°C' % (val,boilingTemperatureCC(val)))
        
    else:
    
        # Sättigungsdampfdruck in Abhängigkeit von der Temperatur
        temp = val
        print('Temperatur: %s°C' % temp)
        print('Sättigungsdampfdruck:')
        rtn = svp(temp)
        x = rtn['Goff-Gratch']
        for algorithm in rtn:
            print("%-15s %9.4f %7.2f%%" % (algorithm,rtn[algorithm],(rtn[algorithm]-x)/x*100))

else:

    # Tabelle des Sättigungsdampfdruckes über der Temperatur,
    # berechnet nach Goff-Gratch
    print('Goff-Gratch:')
    print(' [°C]    [mbar]')
    for temp in range(985,1006,1):
        x = svpGoffGratch(temp/10)
        print("%5.1f  %9.4f" % (temp/10,x))
