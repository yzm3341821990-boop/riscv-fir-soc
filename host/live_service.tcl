# User-started persistent Quartus link. Runtime mailbox access, no programming.
source [file join [file dirname [file normalize [info script]]] live_link_lib.tcl]
fconfigure stdin -encoding utf-8 -translation auto
# Quartus 17 wraps stdout puts in its own buffered message logger.
# Use the native stderr channel; the Python transport merges stderr/stdout.
fconfigure stderr -encoding utf-8 -translation lf -buffering none
proc live_quote {value} {
    return "\"[string map [list "\\" "\\\\" "\"" "\\\"" "\n" "\\n" "\r" "\\r" "\t" "\\t"] $value]\""
}
set failed [catch {
    load_package insystem_source_probe
    load_package jtag
    set info [fir_live::connect]
    puts stderr "LIVE_READY \{\"token\":[dict get $info token],\"hardware\":[live_quote [dict get $info hardware]],\"device\":[live_quote [dict get $info device]],\"instance\":[dict get $info instance]\}"
    flush stderr
    while {[gets stdin line]>=0} {
        if {$line eq "QUIT"} {break}
        if {![regexp {^X ([0-9A-Fa-f]{80})$} $line unused request]} {error "Unsupported LIV0 service command"}
        puts stderr "LIVE_R [fir_live::exchange $request]";flush stderr
    }
} message]
set close_failed [catch {fir_live::disconnect} close_message]
if {$failed} {puts stderr "LIVE_ERROR [live_quote $message]";flush stderr;error $message}
if {$close_failed} {puts stderr "LIVE_ERROR [live_quote $close_message]";flush stderr;error $close_message}
puts stderr LIVE_BYE
flush stderr
