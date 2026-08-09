Output "/tmp/computeledger-demo/docs/demo-run-wrap.gif"
Set FontSize 16
Set Width 760
Set Height 260
Set Theme "Dracula"
Set WindowBar Colorful
Set WindowBarSize 36

Type "export PS1='$ '"
Enter
Sleep 300ms
Type "export HOME=/tmp/computeledger-demo"
Enter
Sleep 300ms

Type "computeledger keys generate --local"
Enter
Sleep 1s

Type "computeledger run --local --provider on-prem --hardware nvidia-a100 --workload-type training -- sleep 1"
Enter
Sleep 3s
