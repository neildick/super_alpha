module tb_alpha_regfile;
    timeunit 1ns;
    timeprecision 1ps;

    typedef logic [4:0] register_index_t;
    typedef logic [63:0] register_word_t;

    logic clk = 1'b0;
    logic write_enable = 1'b0;
    logic [4:0] write_addr = 5'd0;
    logic [63:0] write_data = 64'd0;
    logic [4:0] read_addr_a = 5'd31;
    logic [4:0] read_addr_b = 5'd31;
    wire [63:0] read_data_a;
    wire [63:0] read_data_b;

    alpha_regfile dut (
        .clk_i(clk),
        .write_enable_i(write_enable),
        .write_addr_i(write_addr),
        .write_data_i(write_data),
        .read_addr_a_i(read_addr_a),
        .read_addr_b_i(read_addr_b),
        .read_data_a_o(read_data_a),
        .read_data_b_o(read_data_b)
    );

    string selected_test;
    string active_test;
    integer tests_run = 0;
    integer tests_failed = 0;
    integer checks = 0;
    integer failures = 0;
    integer total_checks = 0;
    integer unsigned initial_seed = 12345;
    integer unsigned random_state;
    logic [63:0] expected [0:31];

    // Explicit generator: the same seed supplies the same traffic in every tool.
    function automatic logic [31:0] next_random();
        random_state = random_state ^ (random_state << 13);
        random_state = random_state ^ (random_state >> 17);
        random_state = random_state ^ (random_state << 5);
        return random_state;
    endfunction

    function automatic logic [63:0] initial_value(input integer index);
        return 64'h8123_4567_89ab_cdef ^ (64'h0101_0101_0101_0101 * register_word_t'(index));
    endfunction

    task automatic check_value(
        input logic [63:0] actual,
        input logic [63:0] wanted,
        input string detail
    );
        checks = checks + 1;
        if (actual !== wanted) begin
            failures = failures + 1;
            if (failures <= 8)
                $display("SA_CHECK %s %s expected=0x%016h actual=0x%016h",
                         active_test, detail, wanted, actual);
        end
    endtask

    task automatic write_register(
        input logic [4:0] address,
        input logic [63:0] value,
        input logic enable_write
    );
        clk = 1'b0;
        write_addr = address;
        write_data = value;
        write_enable = enable_write;
        #2;
        clk = 1'b1;
        #2;
        clk = 1'b0;
        #2;
        write_enable = 1'b0;
    endtask

    task automatic check_reads(
        input logic [4:0] address_a,
        input logic [63:0] value_a,
        input logic [4:0] address_b,
        input logic [63:0] value_b,
        input string detail
    );
        read_addr_a = address_a;
        read_addr_b = address_b;
        #1;
        check_value(read_data_a, value_a, {detail, " port=A"});
        check_value(read_data_b, value_b, {detail, " port=B"});
    endtask

    task automatic initialize_registers();
        for (integer i = 0; i < 31; i = i + 1) begin
            expected[i] = initial_value(i);
            write_register(register_index_t'(i), expected[i], 1'b1);
        end
        expected[31] = 64'd0;
    endtask

    task automatic test_zero_reads();
        check_reads(5'd31, 64'd0, 5'd31, 64'd0, "zero register");
        write_enable = 1'b0;
        write_data = 64'hffff_ffff_ffff_ffff;
        #1;
        check_reads(5'd31, 64'd0, 5'd31, 64'd0, "zero register remains zero");
    endtask

    task automatic test_write_and_read();
        write_register(5'd3, 64'hfedc_ba98_7654_3210, 1'b1);
        check_reads(5'd3, 64'hfedc_ba98_7654_3210,
                    5'd3, 64'hfedc_ba98_7654_3210, "stored 64-bit value");
        write_register(5'd3, 64'h0123_4567_89ab_cdef, 1'b1);
        check_reads(5'd3, 64'h0123_4567_89ab_cdef,
                    5'd3, 64'h0123_4567_89ab_cdef, "replacement value");
    endtask

    task automatic test_write_enable();
        write_register(5'd5, 64'hffff_0000_aaaa_5555, 1'b1);
        write_register(5'd5, 64'h1234_5678_90ab_cdef, 1'b0);
        check_reads(5'd5, 64'hffff_0000_aaaa_5555,
                    5'd5, 64'hffff_0000_aaaa_5555, "disabled write preserves value");
        write_register(5'd5, 64'd0, 1'b1);
        check_reads(5'd5, 64'd0, 5'd5, 64'd0, "enabled zero write");
    endtask

    task automatic test_edge_timing();
        write_register(5'd7, 64'h1111_2222_3333_4444, 1'b1);
        write_addr = 5'd7;
        write_data = 64'haaaa_bbbb_cccc_dddd;
        write_enable = 1'b1;
        check_reads(5'd7, 64'h1111_2222_3333_4444,
                    5'd7, 64'h1111_2222_3333_4444, "before rising edge");
        clk = 1'b1;
        #1;
        check_reads(5'd7, 64'haaaa_bbbb_cccc_dddd,
                    5'd7, 64'haaaa_bbbb_cccc_dddd, "after rising edge");
        write_data = 64'h9999_8888_7777_6666;
        #1;
        check_reads(5'd7, 64'haaaa_bbbb_cccc_dddd,
                    5'd7, 64'haaaa_bbbb_cccc_dddd, "changing data while clock high");
        clk = 1'b0;
        #1;
        check_reads(5'd7, 64'haaaa_bbbb_cccc_dddd,
                    5'd7, 64'haaaa_bbbb_cccc_dddd, "falling edge preserves value");
        write_enable = 1'b0;
    endtask

    task automatic test_independent_reads();
        initialize_registers();
        // Clock stays low while both read addresses change.
        for (integer a = 0; a < 32; a = a + 1)
            for (integer b = 0; b < 32; b = b + 1)
                check_reads(register_index_t'(a), expected[a], register_index_t'(b), expected[b],
                            $sformatf("addresses A=%0d B=%0d", a, b));
    endtask

    task automatic test_zero_writes();
        write_register(5'd31, 64'hffff_ffff_ffff_ffff, 1'b1);
        check_reads(5'd31, 64'd0, 5'd31, 64'd0, "write to R31 discarded");
        write_register(5'd31, 64'h0123_4567_89ab_cdef, 1'b1);
        check_reads(5'd31, 64'd0, 5'd31, 64'd0, "second write to R31 discarded");
    endtask

    task automatic test_random_scoreboard();
        logic [31:0] choice;
        logic [31:0] high_bits;
        logic [31:0] low_bits;
        logic [4:0] a;
        logic [4:0] b;
        logic [4:0] destination;
        logic enable_write;
        logic [63:0] value;
        initialize_registers();
        for (integer cycle = 0; cycle < 512; cycle = cycle + 1) begin
            choice = next_random();
            a = choice[4:0];
            b = choice[9:5];
            destination = choice[14:10];
            enable_write = choice[15];
            high_bits = next_random();
            low_bits = next_random();
            value = {high_bits, low_bits};
            check_reads(a, expected[a], b, expected[b],
                        $sformatf("cycle=%0d before edge", cycle));
            write_register(destination, value, enable_write);
            if (enable_write && destination != 5'd31)
                expected[destination] = value;
            check_reads(destination, expected[destination], a, expected[a],
                        $sformatf("cycle=%0d after edge", cycle));
        end
        // Check all words after the traffic, including R31.
        for (integer i = 0; i < 32; i = i + 1)
            check_reads(register_index_t'(i), expected[i], register_index_t'(31-i), expected[31-i], "final state");
    endtask

    task automatic run_test(input string name);
        if (selected_test == "all" || selected_test == name) begin
            active_test = name;
            checks = 0;
            failures = 0;
            tests_run = tests_run + 1;
            case (name)
                "zero_reads":         test_zero_reads();
                "write_and_read":     test_write_and_read();
                "write_enable":       test_write_enable();
                "edge_timing":        test_edge_timing();
                "independent_reads":  test_independent_reads();
                "zero_writes":        test_zero_writes();
                "random_scoreboard":  test_random_scoreboard();
                default: $fatal(1, "Unknown test %s", name);
            endcase
            total_checks = total_checks + checks;
            if (failures != 0)
                tests_failed = tests_failed + 1;
            $display("SA_RESULT %s %s checks=%0d failures=%0d", name,
                     failures == 0 ? "PASS" : "FAIL", checks, failures);
        end
    endtask

`ifdef VERILATOR
    initial begin
        if ($test$plusargs("WAVES")) begin
            $dumpfile("trace.vcd");
            $dumpvars(0, tb_alpha_regfile);
        end
    end
`endif

    initial begin
        if (!$value$plusargs("TEST=%s", selected_test))
            selected_test = "all";
        if ($value$plusargs("SEED=%d", initial_seed)) begin end
        if (initial_seed == 0)
            $fatal(1, "SEED must be nonzero");
        random_state = initial_seed;
        #1;
        run_test("zero_reads");
        run_test("write_and_read");
        run_test("write_enable");
        run_test("edge_timing");
        run_test("independent_reads");
        run_test("zero_writes");
        run_test("random_scoreboard");
        if (tests_run == 0)
            $fatal(1, "Unknown TEST=%s", selected_test);
        $display("SA_SUMMARY tests=%0d failed=%0d checks=%0d seed=%0d",
                 tests_run, tests_failed, total_checks, initial_seed);
        $finish;
    end

    initial begin
        #1000000;
        $fatal(1, "Testbench simulation-time limit exceeded");
    end
endmodule
