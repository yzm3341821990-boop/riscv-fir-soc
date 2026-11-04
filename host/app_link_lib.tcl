# CPU5 runtime link. Loading this library alone never opens a JTAG session.
namespace eval fir_live {variable instance;variable token 0;variable connected 0}
proc fir_live::number {hex} {
    if {![regexp {^[0-9A-Fa-f]{1,80}$} $hex]} {error "Malformed 320-bit JTAG value"}
    return [expr 0x$hex]
}
proc fir_live::target_device {device} {
    if {[regexp -nocase {\(0x([0-9a-f]{8})\)[[:space:]]*$} $device unused idcode]} {
        return [string equal -nocase $idcode 020F70DD]
    }
    return [string match *EP4CE115* $device]
}
proc fir_live::disconnect {} {
    variable connected
    if {$connected} {set connected 0;end_insystem_source_probe}
}
proc fir_live::connect {} {
    variable instance;variable token;variable connected
    if {$connected} {error "A CPU5 session is already open"}
    set matches {};set failures {};set old_image 0
    foreach hardware [get_hardware_names] {
        if {![regexp {^USB-Blaster( |$)} $hardware]} {continue}
        if {[catch {get_device_names -hardware_name $hardware} devices]} {lappend failures $devices;continue}
        foreach device $devices {
            if {![target_device $device]} {continue}
            if {[catch {get_insystem_source_probe_instance_info -hardware_name $hardware -device_name $device} rows]} {
                lappend failures "$hardware / $device: $rows";continue
            }
            foreach row $rows {
                if {[llength $row]!=4} {continue}
                if {[lindex $row 3] in {FIR0 LIV0 CPU0 CPU1 CPU2 CPU3 CPU4}} {set old_image 1}
                if {[lindex $row 1]==320 && [lindex $row 2]==320 && [lindex $row 3] eq "CPU5"} {
                    lappend matches [list $hardware $device [lindex $row 0]]
                }
            }
        }
    }
    if {[llength $failures]} {error "JTAG discovery failed: [join $failures {; }]"}
    if {[llength $matches]!=1} {
        if {$old_image} {error "The board is running an older image. Program the step33 CPU5 SOF first."}
        error "Expected one CPU5 320/320 instance on the original 6 MHz USB-Blaster; found [llength $matches]."
    }
    set selected [lindex $matches 0];set hardware [lindex $selected 0];set device [lindex $selected 1];set instance [lindex $selected 2]
    start_insystem_source_probe -hardware_name $hardware -device_name $device
    set connected 1
    set code [catch {
        set source [number [string trim [read_source_data -instance_index $instance -value_in_hex]]]
        set token [expr ($source>>311)&1]
        set deadline [expr [clock milliseconds]+8000];set settled 0
        while {[clock milliseconds]<$deadline} {
            set p [number [string trim [read_probe_data -instance_index $instance -value_in_hex]]]
            if {($p>>312)!=0x4c || (($p>>258)&255)!=1} {error "Wrong CPU5 protocol signature"}
            if {(($p>>311)&1)==$token} {set settled 1;break}
            after 2
        }
        if {!$settled} {error "Previous CPU5 command did not settle"}
    } message]
    if {$code} {catch {disconnect};error $message}
    return [dict create token $token hardware $hardware device $device instance $instance]
}
proc fir_live::exchange {request_hex} {
    variable instance;variable token;variable connected
    if {!$connected} {error "CPU5 is not connected"}
    if {![regexp {^[0-9A-Fa-f]{80}$} $request_hex]} {error "CPU5 request must contain exactly 80 hexadecimal characters"}
    set request [number $request_hex];set next_token [expr ($request>>311)&1]
    if {$next_token==$token} {error "CPU5 request did not toggle its token"}
    # Pass the full string; Tcl 8.5/Win32 format %X would truncate wide values.
    write_source_data -instance_index $instance -value $request_hex -value_in_hex
    set mask [expr ((1<<38)-1)<<274];set deadline [expr [clock milliseconds]+8000]
    set previous {};set stable 0
    while {[clock milliseconds]<$deadline} {
        set raw [string toupper [string trim [read_probe_data -instance_index $instance -value_in_hex]]]
        set reply [number $raw]
        if {($reply>>312)!=0x4c || (($reply>>258)&255)!=1} {error "CPU5 probe signature/version changed"}
        if {($reply&$mask)==($request&$mask)} {
            if {$raw eq $previous} {incr stable} else {set stable 1;set previous $raw}
            if {$stable>=2} {set token $next_token;return $raw}
        } else {set previous {};set stable 0}
        after 1
    }
    error "CPU5 acknowledgement timed out; no new frame was accepted by the desktop"
}
