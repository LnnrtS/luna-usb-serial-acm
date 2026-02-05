# This file is Copyright (c) 2021 Greg Davill <greg.davill@gmail.com>
# License: BSD

import os
from pathlib import Path

from amaranth import Record, Signal, Module, Elaboratable, ClockDomain, ClockSignal, ResetSignal

from amaranth.hdl.rec import DIR_FANIN, DIR_FANOUT, DIR_NONE
from amaranth.back import verilog

from luna.full_devices import USBSerialDevice as LunaDeviceACM
from luna.gateware.architecture.car import PHYResetController


def build(
    idVendor=0x1209,
    idProduct=0x5af1,
    manufacturer_string="GSD",
    product_string="ButterStick r1.0 ACM",
    ulpi = False
    ):

    class LunaUSBSerialDevice(Elaboratable):
        """
        Amaranth module that exposes internal interfaces as Signal/Record attributes
        """
        def __init__(self, bus):

            self.bus = bus

            self.usb0 = usb = LunaDeviceACM(
                bus=bus,
                idVendor=idVendor,
                idProduct=idProduct, 
                manufacturer_string=manufacturer_string,
                product_string=product_string
                )
            
            self.rx = Record(usb.rx.layout)
            self.tx = Record(usb.tx.layout)
                
            self.clk_sync = Signal()
            self.clk_usb = Signal()
            self.rst_sync = Signal()

            self.usb_holdoff  = Signal()
            

        def elaborate(self, platform):
            m = Module()

            # Create our clock domains.
            m.domains.sync = ClockDomain()
            m.domains.usb  = ClockDomain()
            m.submodules.usb_reset = controller = PHYResetController(reset_length=40e-3, stop_length=40e-4)
            m.d.comb += [
                ResetSignal("usb")  .eq(controller.phy_reset),
                self.usb_holdoff    .eq(controller.phy_stop)
            ]
            
            # Attach Clock domains
            m.d.comb += [
                ClockSignal(domain="sync")     .eq(self.clk_sync),
                ClockSignal(domain="usb")      .eq(self.clk_usb),
                ResetSignal("sync").eq(self.rst_sync),
            ]
            
            # Attach usb module
            m.submodules.usb0 = self.usb0

            m.d.comb += [
                # Wire up streams
                self.usb0.tx.valid    .eq(self.tx.valid),
                self.usb0.tx.first    .eq(self.tx.first),
                self.usb0.tx.last     .eq(self.tx.last),
                self.usb0.tx.payload  .eq(self.tx.payload),
                # --
                
                self.tx.ready    .eq(self.usb0.tx.ready),


                self.rx.valid    .eq(self.usb0.rx.valid),
                self.rx.first    .eq(self.usb0.rx.first),
                self.rx.last     .eq(self.usb0.rx.last),
                self.rx.payload  .eq(self.usb0.rx.payload),
                # --
                self.usb0.rx.ready    .eq(self.rx.ready),
            
                # ... and always connect by default.
                self.usb0.connect     .eq(1)
            ]
            return m


    raw_pads = Record(
    [
        ("d_p",    [('i', 1, DIR_FANIN), ('o', 1, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
        ("d_n",    [('i', 1, DIR_FANIN), ('o', 1, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
        ("pullup", [('o', 1, DIR_FANIN)]),
    ])

    ulpi_pads = Record(
    [
        ('data', [('i', 8, DIR_FANIN), ('o', 8, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
        ('clk', [('o', 1, DIR_FANOUT)]),
        ('stp', [('o', 1, DIR_FANOUT)]),
        ('nxt', [('i', 1, DIR_FANIN)]),
        ('dir', [('i', 1, DIR_FANIN)]),
        ('rst', [('o', 1, DIR_FANOUT)])
    ])

    elaboratable = LunaUSBSerialDevice(bus = ulpi_pads if ulpi else raw_pads)
    name = 'LunaUSBSerialDevice_ULPI' if ulpi else 'LunaUSBSerialDevice_RAW'

    ports = []

    # Patch through all Records/Ports
    for port_name, port in vars(elaboratable).items():
        if not port_name.startswith("_") and isinstance(port, (Signal, Record)):
            ports += port._lhs_signals()

    verilog_text = verilog.convert(elaboratable, name=name, ports=ports, strip_internal_attrs=True)

    vdir = Path(__file__).parent / "verilog"
    os.makedirs(vdir, exist_ok=True)

    verilog_file = vdir / f"{name}.v"

    with open(verilog_file, "w") as f:
        f.write(verilog_text)

    return verilog_file, name


