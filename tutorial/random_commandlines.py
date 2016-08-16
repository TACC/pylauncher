import random;

max_wait = 20;
with open("random_command_lines","w") as lines:
    for i in range(100):
        lines.write("./random_wait %d\n" % int(max_wait * random.random()))
