`default_nettype none
`timescale 1ns / 1ps

// Cocotb-driven testbench for tt_um_whack_a_mole
module tb();

  // Waveform dump
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
    // Dump the internal timer for visibility
    $dumpvars(0, dut.timer_inst.count);
    $dumpvars(0, dut.timer_inst.game_end);
  end

  // Clock: 1 MHz (1000ns period)
  reg clk = 0;
  initial forever #500 clk = ~clk;  // Half period = 500ns

  // DUT inputs: cocotb will drive these
  reg        rst_n  = 1;
  reg  [7:0] ui_in  = 8'd0;    // Buttons
  reg  [7:0] uio_in = 8'd0;    // Unused in this design
  reg        ena    = 1'b1;    // Always enabled

  // DUT outputs
  wire [7:0] uo_out;           // 7-segment + DP
  wire [7:0] uio_out;          // Score LEDs
  wire [7:0] uio_oe;           // Always 1’s
  wire       game_end;         // Exposed end‐of‐game flag

  // Instantiate the DUT, now with game_end exposed
  tt_um_whack_a_mole dut (
    .ui_in      (ui_in),
    .uo_out     (uo_out),
    .uio_in     (uio_in),
    .uio_out    (uio_out),
    .uio_oe     (uio_oe),
    .ena        (ena),
    .clk        (clk),
    .rst_n      (rst_n),
    .game_end   (game_end)
  );

endmodule

`default_nettype wire
