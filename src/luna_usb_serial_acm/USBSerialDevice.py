# This file is Copyright (c) 2023-2021 Greg Davill <greg.davill@gmail.com>
# License: BSD

from migen import Module, TSTriple, ClockSignal, ResetSignal, Instance
# import litex
from litex.soc.interconnect import stream

from .build_verilog import build


class USBSerialDevice(Module):
    """
    Wrapper for compiled amaranth module
    """
    def __init__(self, platform, usb_pads, stream_clockdomain="sys", usb_clockdomain="usb", usb_io_clockdomain="usb_io"):

        verilog_file, module_name = build()

        # Attach verilog block to module
        platform.add_source(verilog_file)
        dp = TSTriple(1)
        dn = TSTriple(1)

        # Stream interface in/out of logic
        self.sink = self.usb_tx = stream.Endpoint([("data", 8)])
        self.source = self.usb_rx = stream.Endpoint([("data", 8)])

        # Add clock domain crossing FIFOs
        tx_cdc = stream.ClockDomainCrossing([("data", 8)], stream_clockdomain, usb_clockdomain)
        rx_cdc = stream.ClockDomainCrossing([("data", 8)], usb_clockdomain, stream_clockdomain)
        self.submodules += tx_cdc, rx_cdc
        
        self.comb += [
            self.usb_tx.connect(tx_cdc.sink),
            rx_cdc.source.connect(self.usb_rx),
        ]
        
        self.specials += [
            dp.get_tristate(usb_pads.d_p),
            dn.get_tristate(usb_pads.d_n),
        ]
            

        self.params = dict(
            # Clock / Reset
            i_clk_usb   = ClockSignal(usb_clockdomain),
            i_clk_sync   = ClockSignal(usb_clockdomain),
            i_rst_sync   = ResetSignal(usb_clockdomain),

            i_usb_io_clk = ClockSignal(usb_io_clockdomain),
            i_usb_io_rst = ResetSignal(usb_io_clockdomain),

            # IO
            o_raw_usb__d_p__o = dp.o,
            o_raw_usb__d_p__oe = dp.oe,
            i_raw_usb__d_p__i = dp.i,
            o_raw_usb__d_n__o = dn.o,
            o_raw_usb__d_n__oe = dn.oe,
            i_raw_usb__d_n__i = dn.i,
            o_raw_usb__pullup__o = usb_pads.pullup,

            # Tx stream (Data out: USB device to computer)
            o_tx__ready = tx_cdc.source.ready,
            i_tx__valid = tx_cdc.source.valid,
            i_tx__first = tx_cdc.source.first,
            i_tx__last = tx_cdc.source.last,
            i_tx__payload = tx_cdc.source.data,
            
            # Rx Stream (Data in: From a Computer to USB Device)
            i_rx__ready = rx_cdc.sink.ready,
            o_rx__valid = rx_cdc.sink.valid,
            o_rx__first = rx_cdc.sink.first,
            o_rx__last = rx_cdc.sink.last,
            o_rx__payload = rx_cdc.sink.data,
        )

        self.specials += Instance(module_name,
            **self.params
        )
