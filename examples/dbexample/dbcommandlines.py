import random;

max_wait = 60;
with open("db_command_lines","w") as lines:
    for i in range(100):
        lines.write("python todb.py PYL_ID %d\n" % int(max_wait * random.random()))
