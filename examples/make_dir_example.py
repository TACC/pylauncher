import os

mod = 5
n = 70

f = open("modcommandlines","w")

for i in range(n):
    dirname = "pylauncher_tmpdir%d" % (i%5)
    if not os.path.isdir(dirname):
        os.mkdir(dirname)
    f.write("cd %s ; touch touch%d\n" % (dirname,i))

f.close()
