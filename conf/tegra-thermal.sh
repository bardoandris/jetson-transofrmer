#!/bin/bash
# from https://rmauro.dev/monitor-jetson-orin-nano-temperature-in-real-time-with-a-bash-script/
# Restore the cursor on exit
trap 'tput cnorm' EXIT

# Hide the cursor for cleaner output
tput civis

# Process the first tegrastats output line
tegrastats | while read -r line; do
    clear

    highest_temp=$(echo "$line" |
        grep -oP '(?:cpu|gpu|soc[0-2]|tj)@\K[0-9]+(?:\.[0-9]+)?' |
        LC_ALL=C awk 'NR == 1 || $1 > highest { highest = $1 } END { if (NR) print highest }')

    echo $highest_temp
    break
done
