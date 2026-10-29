library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_shared_ram_m9k is end entity;
architecture test of tb_shared_ram_m9k is
    subtype word is std_logic_vector(31 downto 0);
    signal clk : std_logic := '0';
    signal rst : std_logic := '1';
    signal aq,aw,bq,bw,allow_b,ready_b,valid_b : std_logic := '0';
    signal be : std_logic_vector(3 downto 0) := "1111";
    signal aa,ad,ar,ba,bd,br : word := (others=>'0');
    signal finished : boolean := false;
    function address(n : natural) return word is
    begin return std_logic_vector(to_unsigned(n,32)); end;
    function pattern(n : natural) return word is
        variable value : unsigned(31 downto 0);
    begin value:=to_unsigned(37*n+7,32);value:=value xor x"A5A50000";return std_logic_vector(value);end;
begin
    clk<=not clk after 5 ns when not finished else '0';
    dut : entity work.shared_ram_m9k port map(clk,rst,aq,aw,be,aa,ad,ar,
        bq,bw,ba,bd,allow_b,ready_b,valid_b,br);
    watchdog : process begin wait until finished for 1 ms;
        assert finished report "M9K_TEST_TIMEOUT" severity failure;wait;end process;
    stimulus : process
        procedure tick is begin wait until rising_edge(clk);wait for 1 ns;end;
        procedure write_a(n : natural;v : word;mask : std_logic_vector(3 downto 0):="1111") is
        begin aq<='1';aw<='1';aa<=address(n);ad<=v;be<=mask;tick;aq<='0';aw<='0';end;
        procedure read_a(n : natural;expected : word) is
        begin aq<='1';aw<='0';aa<=address(n);tick;
            assert ar=expected report "M9K_A_READ_OR_ALIAS" severity failure;
            aq<='0';end;
        procedure read_b(n : natural;expected : word) is
        begin bq<='1';bw<='0';ba<=address(n);wait for 1 ns;
            assert ready_b='1' report "M9K_B_NOT_READY" severity failure;tick;
            assert valid_b='1' and br=expected report "M9K_B_READ_OR_ALIAS" severity failure;
            bq<='0';tick;
            assert valid_b='0' report "M9K_GHOST_RESPONSE" severity failure;end;
    begin
        tick;
        -- Host loading through A remains legal while CPU/DMA are in reset.
        for n in 0 to 8191 loop write_a(4*n,pattern(n));end loop;
        tick;rst<='0';allow_b<='1';tick;
        for n in 0 to 8191 loop read_b(4*n,pattern(n));end loop;
        write_a(32764,x"AABBCCDD");write_a(32764,x"11223344","0101");
        read_a(32764,x"AA22CC44");write_a(32764,x"0000FF00","0010");
        read_b(32764,x"AA22FF44");write_a(32764,x"55000000","1000");
        read_b(32764,x"5522FF44");
        -- Independent writes accept in the same edge.
        aq<='1';aw<='1';aa<=address(0);ad<=x"12345678";be<="1111";
        bq<='1';bw<='1';ba<=address(4);bd<=x"87654321";wait for 1 ns;
        assert ready_b='1' report "M9K_FALSE_COLLISION" severity failure;tick;
        aq<='0';aw<='0';bq<='0';bw<='0';tick;
        read_b(0,x"12345678");read_a(4,x"87654321");
        -- A write wins now; the held B read receives the new data next edge.
        aq<='1';aw<='1';aa<=address(32764);ad<=x"12345678";
        bq<='1';bw<='0';ba<=address(32764);wait for 1 ns;
        assert ready_b='0' report "M9K_COLLISION_NOT_STALLED" severity failure;tick;
        assert valid_b='0' report "M9K_COLLISION_EARLY_RESPONSE" severity failure;
        aq<='0';aw<='0';tick;
        assert valid_b='1' and br=x"12345678" report "M9K_WRITE_READ_ORDER" severity failure;
        bq<='0';tick;
        -- An A read sees old data; the held B write executes next edge.
        aq<='1';aw<='0';aa<=address(32764);
        bq<='1';bw<='1';ba<=address(32764);bd<=x"DEADBEEF";wait for 1 ns;
        assert ready_b='0' report "M9K_READ_WRITE_COLLISION" severity failure;tick;
        assert ar=x"12345678" report "M9K_READ_WRITE_OLD_VALUE" severity failure;
        aq<='0';tick;bq<='0';bw<='0';tick;read_a(32764,x"DEADBEEF");
        -- Both writes to one word are serialized, including masked A writes.
        aq<='1';aw<='1';aa<=address(8);ad<=x"00000011";be<="0001";
        bq<='1';bw<='1';ba<=address(8);bd<=x"CAFEBABE";wait for 1 ns;
        assert ready_b='0' report "M9K_WRITE_WRITE_COLLISION" severity failure;tick;
        aq<='0';aw<='0';tick;bq<='0';bw<='0';tick;read_a(8,x"CAFEBABE");
        rst<='1';bq<='1';bw<='1';ba<=address(8);bd<=x"00000000";tick;
        assert ready_b='0' and valid_b='0' report "M9K_RESET_DMA" severity failure;
        bq<='0';bw<='0';rst<='0';tick;read_a(8,x"CAFEBABE");
        report "M9K_RAM_PASS words=8192 bytes=32768 byte_masks=3 collision_cases=3" severity note;
        finished<=true;wait;
    end process;
end architecture;
