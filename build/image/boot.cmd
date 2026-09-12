# BliKVM P1: vendor distro scan -> direct read-write SD root.
if test -n "${kernel_addr_r}" && test -n "${fdt_addr_r}"; then
    if load mmc 0:1 ${kernel_addr_r} /boot/Image; then
        if load mmc 0:1 ${fdt_addr_r} /boot/sun50i-h616-blikvm-v4.dtb; then
            setenv bootargs "console=ttyS0,115200n8 earlycon loglevel=6 printk.time=1 root=PARTUUID=b14b0001-01 rootfstype=ext4 rootwait rw net.ifnames=0 panic=-1"
            booti ${kernel_addr_r} - ${fdt_addr_r}
        fi
    fi
fi
echo "BliKVM SD boot failed; halted. Restore recovery SD with power off."
while true; do sleep 60; done
