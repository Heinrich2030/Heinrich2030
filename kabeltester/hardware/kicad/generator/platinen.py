"""Netzlisten der drei Platinen: Kanalkarte, Messkarte, Adapter-Vorlage.

Bezug: kabeltester/docs/hardware.md und firmware/messkarte/src/hardware.h.
"""
from modell import Platine

# Footprints
R0603 = 'Resistor_SMD:R_0603_1608Metric'
R0805 = 'Resistor_SMD:R_0805_2012Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
SOT23_5 = 'Package_TO_SOT_SMD:SOT-23-5'
TSSOP16 = 'Package_SO:TSSOP-16_4.4x5mm_P0.65mm'
TSSOP28 = 'Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm'
SOIC8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
SOIC24W = 'Package_SO:SOIC-24W_7.5x15.4mm_P1.27mm'
IDC34 = 'Connector_IDC:IDC-Header_2x17_P2.54mm_Vertical'
LOCH = 'MountingHole:MountingHole_2.7mm_M2.5_Pad_Via'


def jst_ph(n):
    return f'Connector_JST:JST_PH_B{n}B-PH-K_1x{n:02d}_P2.00mm_Vertical'


# Belegung des 34-poligen Flachbandkabels Messkarte <-> Kanalkarte
def bus_belegung(din, dout, sda, scl, adapt):
    return {1: 'GND', 2: 'HI_F', 3: 'GND', 4: 'HI_S', 5: 'GND', 6: 'LO_F', 7: 'GND', 8: 'LO_S', 9: 'GND',
            10: '5VA', 11: '5VA', 12: '3V3', 13: '3V3', 14: 'GND',
            15: 'HA0', 16: 'HA1', 17: 'HA2', 18: 'HA3', 19: 'LA0', 20: 'LA1', 21: 'LA2', 22: 'LA3', 23: 'GND',
            24: 'SR_CLK', 25: 'SR_LATCH', 26: 'SR_OE_N', 27: din, 28: dout, 29: 'GND',
            30: sda, 31: scl, 32: adapt, 33: 'GND', 34: 'GND'}


def befestigung(p, n=4):
    for _ in range(n):
        p.teil('H', 'Mechanical:MountingHole_Pad', 'M2.5', LOCH, {1: 'GND'})


# ---------------------------------------------------------------------------
def kanalkarte():
    p = Platine('kanalkarte', 'Kabeltester Kanalkarte (64 Testpunkte)')

    # --- Hauptblatt: Steckverbinder, Schieberegister, Versorgung
    din = {f'a{i}': f'TP{i}' for i in range(1, 33)}
    din.update({f'c{i}': f'TP{i + 32}' for i in range(1, 33)})
    din.update({f'b{i}': 'GND' for i in (1, 2, 3, 4, 9, 10)})
    din.update({'b5': '3V3_ADP', 'b6': '3V3_ADP', 'b7': 'SDA', 'b8': 'SCL', 'b32': 'ADAPT_N'})
    p.teil('J', 'kabeltester:DIN41612_C96_Female', 'DIN 41612 C96 Feder', 'Connector_DIN:DIN41612_C_3x32_Female_Vertical_THT',
           din, MPN='Harting DIN-Signal C096 F gerade', Hinweis='Adapter-Schnittstelle')
    p.teil('J', 'Connector_Generic:Conn_02x17_Odd_Even', 'Messkarte', IDC34,
           bus_belegung('SR_DIN', 'SR_DOUT', 'SDA', 'SCL', 'ADAPT_N'), MPN='Wannenstecker 2x17')
    p.teil('F', 'Device:Polyfuse', '50mA', 'Fuse:Fuse_0805_2012Metric', {1: '3V3', 2: '3V3_ADP'}, MPN='Bourns MF-PSMF005X-2')
    # Schieberegister: erstes = Force-Enables (aktiv high), zweites = Sense-Enables (aktiv low)
    force = {15: 'ENF_HI0', 1: 'ENF_HI1', 2: 'ENF_HI2', 3: 'ENF_HI3', 4: 'ENF_LO0', 5: 'ENF_LO1', 6: 'ENF_LO2', 7: 'ENF_LO3'}
    sense = {15: 'ENS_HI0_N', 1: 'ENS_HI1_N', 2: 'ENS_HI2_N', 3: 'ENS_HI3_N', 4: 'ENS_LO0_N', 5: 'ENS_LO1_N', 6: 'ENS_LO2_N', 7: 'ENS_LO3_N'}
    for ausg, ser, qh in ((force, 'SR_DIN', 'SR_MITTE'), (sense, 'SR_MITTE', 'SR_DOUT')):
        pins = {16: '3V3', 8: 'GND', 10: '3V3', 11: 'SR_CLK', 12: 'SR_LATCH', 13: 'SR_OE_N', 14: ser, 9: qh}
        pins.update(ausg)
        p.teil('U', '74xx:74HC595', 'SN74HC595PW', TSSOP16, pins, LCSC='C5947')
        p.entkoppeln('3V3')
    # Ruhepegel bei hochohmigen Schieberegistern (/OE high): alles aus
    for netz in force.values():
        p.R('10k', netz, 'GND', LCSC='C25804')
    for netz in sense.values():
        p.R('10k', netz, '5VA', LCSC='C25804')
    p.C('22u', '5VA', 'GND', C1206)
    p.C('10u', '3V3', 'GND', C0805, LCSC='C15850')
    befestigung(p)

    # --- vier Blöcke à 16 Kanäle
    for b in range(4):
        p.neues_blatt(f'Block {b + 1} (TP{b * 16 + 1}-TP{b * 16 + 16})')
        kanaele = range(b * 16, b * 16 + 16)
        for seite, adr, enf, ens, bus_f, bus_s in (('HI', 'HA', f'ENF_HI{b}', f'ENS_HI{b}_N', 'HI_F', 'HI_S'),
                                                   ('LO', 'LA', f'ENF_LO{b}', f'ENS_LO{b}_N', 'LO_F', 'LO_S')):
            pins = {1: '5VA', 27: 'GND', 12: 'GND', 28: bus_f, 17: f'{adr}0', 16: f'{adr}1', 15: f'{adr}2', 14: f'{adr}3', 18: enf}
            s_pins = [19, 20, 21, 22, 23, 24, 25, 26, 11, 10, 9, 8, 7, 6, 5, 4]   # S1..S16
            for k, n in enumerate(kanaele):
                pins[s_pins[k]] = f'F{n + 1}'
            p.teil('U', 'kabeltester:ADG1606', 'ADG1606BRUZ', TSSOP28, pins, LCSC='C208204', Pruefen='Pinbelegung')
            p.entkoppeln('5VA')
            i_pins = [9, 8, 7, 6, 5, 4, 3, 2, 23, 22, 21, 20, 19, 18, 17, 16]  # I0..I15
            pins = {24: '5VA', 12: 'GND', 1: bus_s, 10: f'{adr}0', 11: f'{adr}1', 14: f'{adr}2', 13: f'{adr}3', 15: ens}
            for k, n in enumerate(kanaele):
                pins[i_pins[k]] = f'S{n + 1}'
            p.teil('U', '74xx:CD74HC4067M', 'CD74HCT4067M96', SOIC24W, pins)
            p.entkoppeln('5VA')
        for n in kanaele:
            tp = f'TP{n + 1}'
            p.R('33', tp, f'FR{n + 1}', R1206, MPN='CRCW120633R0FKEAHP', Hinweis='impulsfest')
            p.teil('F', 'Device:Polyfuse', '100mA', 'Fuse:Fuse_1206_3216Metric', {1: f'FR{n + 1}', 2: f'F{n + 1}'},
                   MPN='Bourns MF-USMF010-2')
            p.teil('D', 'kabeltester:BAV199', 'BAV199', SOT23, {3: f'F{n + 1}', 1: 'GND', 2: '5VA'})
            p.R('1k', tp, f'S{n + 1}', R0603, LCSC='C21190')
            p.teil('D', 'kabeltester:BAV199', 'BAV199', SOT23, {3: f'S{n + 1}', 1: 'GND', 2: '5VA'})
            if n % 2 == 0:
                p.teil('D', 'kabeltester:PESD2CAN', 'PESD2CAN', SOT23, {1: tp, 2: f'TP{n + 2}', 3: 'GND'})
    return p


# ---------------------------------------------------------------------------
def messkarte():
    p = Platine('messkarte', 'Kabeltester Messkarte')

    # --- Hauptblatt: Versorgung, Pico 2, Steckverbinder
    p.teil('J', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB-C 5V',
           'Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',
           {'A4': 'VBUS_IN', 'A9': 'VBUS_IN', 'B4': 'VBUS_IN', 'B9': 'VBUS_IN', 'A1': 'GND', 'A12': 'GND', 'B1': 'GND',
            'B12': 'GND', 'S1': 'GND', 'A5': 'CC1', 'B5': 'CC2'}, MPN='GCT USB4105-GF-A')
    p.R('5.1k', 'CC1', 'GND', LCSC='C23186')
    p.R('5.1k', 'CC2', 'GND', LCSC='C23186')
    p.teil('F', 'Device:Polyfuse', '2A', 'Fuse:Fuse_1812_4532Metric', {1: 'VBUS_IN', 2: '+5V'})
    p.teil('D', 'Device:D_TVS', 'SMAJ5.0CA', 'Diode_SMD:D_SMA', {1: '+5V', 2: 'GND'})
    p.C('22u', '+5V', 'GND', C1206)
    p.teil('FB', 'Device:FerriteBead', '600R@100MHz', 'Inductor_SMD:L_0805_2012Metric', {1: '+5V', 2: '5VA'})
    p.C('22u', '5VA', 'GND', C1206)
    p.entkoppeln('5VA')
    p.teil('D', 'Device:D_Schottky', 'SS14', 'Diode_SMD:D_SMA', {1: 'VSYS', 2: '+5V'}, LCSC='C2480')
    pico = {3: 'GND', 8: 'GND', 13: 'GND', 18: 'GND', 23: 'GND', 28: 'GND', 33: 'GND', 38: 'GND',
            39: 'VSYS', 36: '3V3',
            1: 'UART_TX', 2: 'UART_RX', 4: 'SDA_B', 5: 'SCL_B', 9: 'ADAPT_A_N', 10: 'ADAPT_B_N', 11: 'KARTEN_CD',
            14: 'LED_GUT', 15: 'LED_FEHL', 16: 'SDA_A', 17: 'SCL_A', 19: 'START', 20: 'BUZZER',
            21: 'MISO', 22: 'ADS_CS', 24: 'SR_CLK', 25: 'MOSI', 26: 'ADS_DRDY', 27: 'SR_LATCH', 29: 'SR_OE_N',
            31: 'SCAN_ADC', 32: 'REF_MON'}
    p.teil('U', 'kabeltester:RaspberryPi_Pico2', 'Raspberry Pi Pico 2', 'kabeltester:RaspberryPi_Pico2_THT', pico,
           MPN='Raspberry Pi SC1631')
    p.C('10u', '3V3', 'GND', C0805, LCSC='C15850')
    # Flachbandkabel zu den Kanalkarten A und B
    p.teil('J', 'Connector_Generic:Conn_02x17_Odd_Even', 'Kanalkarte A', IDC34,
           bus_belegung('SR_D1', 'SR_D2', 'SDA_XA', 'SCL_XA', 'ADAPT_A_N'))
    p.teil('J', 'Connector_Generic:Conn_02x17_Odd_Even', 'Kanalkarte B', IDC34,
           bus_belegung('SR_D2', 'NC_SR_D3', 'SDA_XB', 'SCL_XB', 'ADAPT_B_N'))
    for netz, x in (('SDA_A', 'SDA_XA'), ('SCL_A', 'SCL_XA'), ('SDA_B', 'SDA_XB'), ('SCL_B', 'SCL_XB')):
        p.R('100', netz, x, LCSC='C22775')
        p.R('4.7k', netz, '3V3', LCSC='C23162')
    for netz in ('ADAPT_A_N', 'ADAPT_B_N', 'SR_OE_N'):
        p.R('10k', netz, '3V3', LCSC='C25804')
    p.teil('JP', 'Jumper:SolderJumper_2_Open', 'Karten C+D', 'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm',
           {1: 'KARTEN_CD', 2: 'GND'})
    # Bedienung und Anzeige
    p.teil('J', 'Connector_Generic:Conn_01x04', 'Display UART', jst_ph(4), {1: 'GND', 2: 'UART_TX', 3: 'UART_RX'})
    p.teil('J', 'Connector_Generic:Conn_01x02', 'Display 5V', jst_ph(2), {1: '+5V', 2: 'GND'})
    p.teil('J', 'Connector_Generic:Conn_01x03', 'LED-Streifen', jst_ph(3), {1: '+5V', 2: 'LED_GUT_K', 3: 'LED_FEHL_K'})
    p.teil('J', 'Connector_Generic:Conn_01x04', 'Start-Taster', jst_ph(4), {1: 'GND', 2: 'START_EXT', 3: 'TASTER_LED'})
    p.teil('J', 'Connector_Generic:Conn_01x02', 'Fussschalter', jst_ph(2), {1: 'GND', 2: 'START_EXT'})
    p.R('100', 'START_EXT', 'START', LCSC='C22775')
    p.C('100n', 'START', 'GND', LCSC='C14663')
    p.R('150', '3V3', 'TASTER_LED')
    for gp, last in (('LED_GUT', 'LED_GUT_K'), ('LED_FEHL', 'LED_FEHL_K'), ('BUZZER', 'BZ_K')):
        p.R('100', gp, f'{gp}_G', LCSC='C22775')
        p.R('100k', f'{gp}_G', 'GND', LCSC='C25803')
        p.teil('Q', 'Transistor_FET:AO3400A', 'AO3400A', SOT23, {1: f'{gp}_G', 2: 'GND', 3: last}, LCSC='C20917')
    p.teil('BZ', 'Device:Buzzer', 'Piezo 12mm', 'Buzzer_Beeper:Buzzer_12x9.5RM7.6', {1: '+5V', 2: 'BZ_K'}, MPN='TDK PS1240P02BT')
    p.R('1k', '+5V', 'BZ_K', LCSC='C21190')
    befestigung(p)

    # --- Blatt Steuerung: Schieberegister (Adressen + Modus)
    p.neues_blatt('Steuerung')
    adr = {15: 'HA0', 1: 'HA1', 2: 'HA2', 3: 'HA3', 4: 'LA0', 5: 'LA1', 6: 'LA2', 7: 'LA3'}
    modus = {15: 'M_HI_QUELLE', 1: 'M_LO_SENKE', 2: 'SH_A0', 3: 'SH_A1', 4: 'M_SCAN_PU', 5: 'M_SCAN_PD', 6: 'M_ISO', 7: 'M_LO_GND'}
    for ausg, ser, qh in ((adr, 'MOSI', 'SR_ZWISCHEN'), (modus, 'SR_ZWISCHEN', 'SR_D1')):
        pins = {16: '3V3', 8: 'GND', 10: '3V3', 11: 'SR_CLK', 12: 'SR_LATCH', 13: 'SR_OE_N', 14: ser, 9: qh}
        pins.update(ausg)
        p.teil('U', '74xx:74HC595', 'SN74HC595PW', TSSOP16, pins, LCSC='C5947')
        p.entkoppeln('3V3')
    for netz in modus.values():
        p.R('100k', netz, 'GND', LCSC='C25803')   # Modus aus, solange /OE high

    # --- Blatt Frontend: Quelle, Stromsenke, Schalter, ADC
    p.neues_blatt('Messfrontend')
    p.teil('U', 'Reference_Voltage:REF5025AD', 'REF5025AIDR', SOIC8,
           {2: '5VA', 4: 'GND', 6: 'REF2V5', 5: 'REF_NR'})
    p.C('1u', 'REF_NR', 'GND', LCSC='C15849')
    p.C('10u', 'REF2V5', 'GND', C0805, LCSC='C15850')
    p.entkoppeln('5VA')
    # Sollwert 100 mV und REF/2
    p.R('24k 0.1%', 'REF2V5', 'SOLL_100M')
    p.R('1k 0.1%', 'SOLL_100M', 'GND', LCSC='C21190')
    p.C('100n', 'SOLL_100M', 'GND', LCSC='C14663')
    p.R('10k', 'REF2V5', 'REF_HALB', LCSC='C25804')
    p.R('10k', 'REF_HALB', 'GND', LCSC='C25804')
    # OPV 1: A = Puffer 2,5 V (HI-Quelle), B = Regler der Stromsenke
    p.teil('U', 'Amplifier_Operational:OPA2376xxD', 'OPA2388IDR', SOIC8,
           {3: 'REF2V5', 2: 'QUELLE', 1: 'QUELLE', 5: 'SOLL_100M', 6: 'SENKE_FB', 7: 'SENKE_OUT', 8: '5VA', 4: 'GND'})
    p.entkoppeln('5VA')
    p.R('1k', 'SH_SENSE', 'SENKE_FB', LCSC='C21190')
    p.C('1n', 'SENKE_OUT', 'SENKE_FB', LCSC='C1588')
    p.R('100', 'SENKE_OUT', 'SENKE_G', LCSC='C22775')
    p.teil('Q', 'Transistor_FET:DMN3404L', 'DMN3404L', SOT23, {1: 'SENKE_G', 2: 'SH_F', 3: 'SENKE_D'})
    # Shunt-Auswahl: Force- und Sense-Pfad getrennt (Ron fällt aus der Messung heraus)
    for d in ('SH_F', 'SH_SENSE'):
        p.teil('U', 'Analog_Switch:ADG1408YRUZ', 'ADG1408YRUZ', TSSOP16,
               {1: 'SH_A0', 16: 'SH_A1', 15: 'GND', 2: '5VA', 3: 'GND', 13: '5VA', 14: 'GND', 8: d,
                4: 'SH1', 5: 'SH2', 6: 'SH3', 7: 'SH4'})
        p.entkoppeln('5VA')
    for netz, wert in (('SH1', '10 0.1%'), ('SH2', '100 0.1%'), ('SH3', '1k 0.1%'), ('SH4', '10k 0.1%')):
        p.R(wert, netz, 'GND', R0805, MPN='Vishay TNPW0805 0.1% 10ppm')
    # Moduswahl mit TMUX1101 (Pin 4 = SEL, aktiv high)
    for a, b, sel in (('QUELLE', 'HI_F', 'M_HI_QUELLE'), ('SENKE_D', 'LO_F', 'M_LO_SENKE'),
                      ('PU_KNOTEN', 'HI_F', 'M_SCAN_PU'), ('PD_KNOTEN', 'LO_F', 'M_SCAN_PD'),
                      ('ISO_KNOTEN', 'HI_F', 'M_ISO'), ('GND', 'LO_F', 'M_LO_GND')):
        p.teil('U', 'Analog_Switch:TMUX1101DBV', 'TMUX1101DBVR', SOT23_5, {1: a, 2: b, 4: sel, 5: '5VA', 3: 'GND'})
        p.entkoppeln('5VA')
    p.R('1k', '3V3', 'PU_KNOTEN', LCSC='C21190')
    p.R('10k', 'PD_KNOTEN', 'GND', LCSC='C25804')
    p.R('1M 0.1%', '5VA', 'ISO_KNOTEN', R0805, MPN='Vishay TNPW08051M00BEEA')
    # ADS1220
    p.R('100', 'HI_S', 'AIN0', LCSC='C22775')
    p.R('100', 'LO_S', 'AIN1', LCSC='C22775')
    p.C('10n', 'AIN0', 'GND', LCSC='C57112')
    p.C('10n', 'AIN1', 'GND', LCSC='C57112')
    p.C('10n', 'AIN0', 'AIN1', LCSC='C57112')
    p.teil('U', 'Analog_ADC:ADS1220xPW', 'ADS1220IPWR', TSSOP16,
           {1: 'SR_CLK', 2: 'ADS_CS', 3: 'GND', 4: 'GND', 5: 'GND', 6: 'REF_HALB', 7: 'SH_SENSE', 8: 'GND', 9: 'GND',
            10: 'AIN1', 11: 'AIN0', 12: '5VA', 13: '3V3', 14: 'ADS_DRDY', 15: 'MISO', 16: 'MOSI'})
    p.entkoppeln('5VA')
    p.entkoppeln('3V3')
    # OPV 2: A = Scan-Puffer (LO-Sense -> RP2350-ADC), B = Monitor REF/2
    p.teil('U', 'Amplifier_Operational:OPA2376xxD', 'OPA2388IDR', SOIC8,
           {3: 'LO_S', 2: 'SCAN_PUF', 1: 'SCAN_PUF', 5: 'REF_HALB', 6: 'REF_MON', 7: 'REF_MON', 8: '5VA', 4: 'GND'})
    p.entkoppeln('5VA')
    p.R('10k', 'SCAN_PUF', 'SCAN_ADC', LCSC='C25804')
    p.R('10k', 'SCAN_ADC', 'GND', LCSC='C25804')
    p.C('1n', 'SCAN_ADC', 'GND', LCSC='C1588')
    return p


# ---------------------------------------------------------------------------
def adapter():
    p = Platine('adapter_rj45', 'Kabeltester Adapter-Vorlage 2x RJ45')
    din = {f'a{i}': f'TP{i}' for i in range(1, 17)}
    din.update({f'b{i}': 'GND' for i in (1, 2, 3, 4, 32)})   # b9/b10 frei lassen (zweilagig nicht anbindbar)
    din.update({'b5': '3V3', 'b6': '3V3', 'b7': 'SDA', 'b8': 'SCL'})
    p.teil('J', 'kabeltester:DIN41612_C96_Male', 'DIN 41612 C96 Messer', 'Connector_DIN:DIN41612_C_3x32_Male_Horizontal_THT',
           din, MPN='Harting DIN-Signal C096 M abgewinkelt')
    for j in range(2):
        p.teil('J', 'Connector:RJ45', f'RJ45 Port {j + 1}', 'Connector_RJ:RJ45_Amphenol_54602-x08_Horizontal',
               {i: f'TP{i + 8 * j}' for i in range(1, 9)}, MPN='Amphenol 54602-908LF')
    p.teil('U', 'Memory_EEPROM:24AA02-OT', '24AA02T-I/OT', SOT23_5, {1: 'SCL', 2: 'GND', 3: 'SDA', 4: '3V3', 5: 'GND'})
    p.entkoppeln('3V3')
    befestigung(p, 2)
    return p
