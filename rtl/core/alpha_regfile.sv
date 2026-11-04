// Exercise 01: implement the integer register file.
// Contract and tests: docs/exercises/01-register-file.md
module alpha_regfile (
    input  logic        clk_i,
    input  logic        write_enable_i,
    input  logic [4:0]  write_addr_i,
    input  logic [63:0] write_data_i,
    input  logic [4:0]  read_addr_a_i,
    input  logic [4:0]  read_addr_b_i,
    output logic [63:0] read_data_a_o,
    output logic [63:0] read_data_b_o
);
    timeunit 1ns;
    timeprecision 1ps;

    logic [63:0] i_regs [30:0];
    logic        wr_addr_zero;
    logic        rd_addr_a_zero;
    logic        rd_addr_b_zero;

    // Register 31 is always read as zero, writes ignored
    assign wr_addr_zero = &write_addr_i;
    assign rd_addr_a_zero = &read_addr_a_i;
    assign rd_addr_b_zero = &read_addr_b_i;

    always_ff @(posedge clk_i) begin
        if (write_enable_i && !wr_addr_zero) begin
            i_regs[write_addr_i] <= write_data_i;
        end
    end

    assign read_data_a_o = rd_addr_a_zero ? '0 : i_regs[read_addr_a_i];
    assign read_data_b_o = rd_addr_b_zero ? '0 : i_regs[read_addr_b_i];
endmodule
