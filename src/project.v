`default_nettype none

// LFSR for segment selection
module rng_lfsr(
    input  wire       clk,
    input  wire       rst_n,
    output reg [2:0]  rand_seg
);
    reg [15:0] lfsr;
    wire feedback = lfsr[0] ^ lfsr[2];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            lfsr <= 16'hACE1;
        else
            lfsr <= {lfsr[14:0], feedback};
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rand_seg <= 3'd0;
        else
            rand_seg <= lfsr[2:0];
    end
endmodule

// 7-segment driver mdoule
module seg7_driver(
    input  wire [2:0]  segment_select,
    input  wire        game_end,
    input  wire [7:0]  score,
    output reg  [6:0]  seg,
    output reg         dp
);
    always @(*) begin
        if (!game_end) begin
            seg = 7'b1111111;
            case (segment_select)
                3'd0: seg[0] = 1'b0;
                3'd1: seg[1] = 1'b0;
                3'd2: seg[2] = 1'b0;
                3'd3: seg[3] = 1'b0;
                3'd4: seg[4] = 1'b0;
                3'd5: seg[5] = 1'b0;
                3'd6: seg[6] = 1'b0;
                default: seg[0] = 1'b0; // default to segment 0 
            endcase
            dp = 1'b1;
        end else begin
            case (score[3:0])
                4'h0: seg = 7'b1000000;
                4'h1: seg = 7'b1111001;
                4'h2: seg = 7'b0100100;
                4'h3: seg = 7'b0110000;
                4'h4: seg = 7'b0011001;
                4'h5: seg = 7'b0010010;
                4'h6: seg = 7'b0000010;
                4'h7: seg = 7'b1111000;
                4'h8: seg = 7'b0000000;
                4'h9: seg = 7'b0010000;
                4'hA: seg = 7'b0001000;
                4'hB: seg = 7'b0000011;
                4'hC: seg = 7'b1000110;
                4'hD: seg = 7'b0100001;
                4'hE: seg = 7'b0000110;
                4'hF: seg = 7'b0001110;
            endcase
            dp = 1'b0;
        end
    end
endmodule

// Game Control FSM (work in progress)
module game_fsm(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [2:0]  rand_seg,
    input  wire [7:0]  btn_sync,
    input  wire        game_end,
    output reg  [2:0]  segment_select,
    output reg  [7:0]  lockout,
    output reg  [7:0]  score_cnt
);
    typedef enum reg [0:0] { WAIT, NEXT } state_t;
    state_t state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            segment_select <= 3'd0;
            lockout        <= 8'd0;
            score_cnt      <= 8'd0;
            state          <= NEXT;
        end else if (!game_end) begin
            case (state)
                NEXT: begin
                    // Pick a new segment
                    segment_select <= (rand_seg == 3'd7) ? 3'd0 : rand_seg;
                    lockout        <= 8'd0;
                    state          <= WAIT;
                end
                WAIT: begin
                    if (btn_sync[segment_select]) begin
                        score_cnt <= score_cnt + 1;
                        state     <= NEXT;
                    end else if (|btn_sync) begin
                        lockout   <= btn_sync;
                        state     <= WAIT;
                    end
                end
            endcase
        end
    end
endmodule

// whack a mole module top
module tt_um_whack_a_mole(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  btn,
    input  wire        game_end,
    output wire [6:0]  seg,
    output wire        dp,
    output wire [7:0]  led_score
);
    wire [2:0] rand_seg;
    wire [2:0] segment_select;
    wire [7:0] lockout;
    wire [7:0] score;
    wire [7:0] btn_sync;

    assign btn_sync   = btn & ~lockout;
    assign led_score  = score;

    rng_lfsr    rng_inst(
        .clk       (clk),
        .rst_n     (rst_n),
        .rand_seg  (rand_seg)
    );

    game_fsm    fsm_inst(
        .clk            (clk),
        .rst_n          (rst_n),
        .rand_seg       (rand_seg),
        .btn_sync       (btn_sync),
        .game_end       (game_end),
        .segment_select (segment_select),
        .lockout        (lockout),
        .score_cnt      (score)
    );

    seg7_driver drv_inst(
        .segment_select (segment_select),
        .game_end       (game_end),
        .score          (score),
        .seg            (seg),
        .dp             (dp)
    );
endmodule

`default_nettype wire