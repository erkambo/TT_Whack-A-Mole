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
  reg [7:0] btn = 8'd0;

  // DUT outputs
  wire [6:0] seg;
  wire        dp;
  wire [7:0]  led_score;
  wire       game_end;

  // Instantiate the whack-a-mole game
  tt_um_whack_a_mole dut (
    .clk        (clk),
    .rst_n      (rst_n),
    .ena        (ena),
    .btn        (btn),
    .seg        (seg),
    .dp         (dp),
    .led_score  (led_score)
  );

endmodule
