Get-ChildItem -Path . -Recurse -Directory -Include "bin", "obj" | Remove-Item -Recurse -Force
