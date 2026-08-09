Output "/tmp/computeledger-demo/docs/demo-export-ledger.gif"
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

Type "computeledger record --local --provider aws --hardware nvidia-h100 --duration-seconds 3600 --gpu-hours 8 --workload-type training"
Enter
Sleep 1s

Type "computeledger ledger list --local --json"
Enter
Sleep 1s

Type "computeledger export --format csv --local --out usage.csv"
Enter
Sleep 2s
