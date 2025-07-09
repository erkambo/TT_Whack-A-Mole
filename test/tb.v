`default_nettype none
`timescale 1ns / 1ps

// Cocotb-driven testbench for reaction_game
module tb();

  // Waveform dump
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);
  end

  // Clock: 1 MHz
  reg clk = 0;
  always #500 clk = ~clk;

  // DUT inputs: let cocotb manage reset and stimulus
  reg rst_n = 1;
  reg ena = 1;
  reg [7:0] ui_in = 8'd0;
  reg [7:0] uio_in = 8'd0;

  // DUT outputs
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  // Instantiate the whack-a-mole game
  tt_um_whack_a_mole dut (
    .clk        (clk),
    .rst_n      (rst_n),
    .ena        (ena),
    .ui_in      (ui_in),
    .uo_out     (uo_out),
    .uio_in     (uio_in),
    .uio_out    (uio_out),
    .uio_oe     (uio_oe)
  );

endmodule
