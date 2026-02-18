"""
Unit tests for pylauncher_core using the standard unittest framework.
"""
import os
import re
import tempfile
import unittest

from pylauncher.pylauncher_core import (
    LauncherException,
    RandomID,
    RandomDir,
    RandomFile,
    RandomNumber,
    CompactIntList,
    pylauncherBarrierString,
    CountedCommandGenerator,
    SleepCommandGenerator,
    SingleSleepCommand,
    Commandline,
    CommandlineGenerator,
    ListCommandlineGenerator,
    FileCommandlineGenerator,
    DynamicCommandlineGenerator,
    Completion,
    WrapCompletion,
    BareCompletion,
    HostDict,
    Node,
    HostLocator,
    HostPoolBase,
    HostPool,
    LocalHostPool,
    LocalExecutor,
)


class TestLauncherException(unittest.TestCase):
    def test_raise_and_str(self):
        msg = "test error message"
        with self.assertRaises(LauncherException) as ctx:
            raise LauncherException(msg)
        self.assertIn(msg, str(ctx.exception))

    def test_exception_is_exception(self):
        self.assertTrue(issubclass(LauncherException, Exception))


class TestRandomID(unittest.TestCase):
    def test_increments(self):
        a = RandomID()
        b = RandomID()
        self.assertIsInstance(a, int)
        self.assertIsInstance(b, int)
        self.assertNotEqual(a, b)


class TestRandomDir(unittest.TestCase):
    def test_returns_string(self):
        d = RandomDir()
        self.assertIsInstance(d, str)
        self.assertTrue(d.startswith("./pylauncher_tmpdir"))

    def test_contains_number(self):
        d = RandomDir()
        self.assertTrue(re.search(r"\d+", d) is not None)


class TestRandomFile(unittest.TestCase):
    def test_returns_string(self):
        f = RandomFile()
        self.assertIsInstance(f, str)
        self.assertIn("pylauncher_tmpfile", f)

    def test_base_suffix(self):
        f = RandomFile(base="mytest")
        self.assertIn("mytest", f)


class TestRandomNumber(unittest.TestCase):
    def test_in_range(self):
        for _ in range(20):
            n = RandomNumber(10, tmin=2)
            self.assertGreaterEqual(n, 2)
            self.assertLessEqual(n, 10)

    def test_single_value(self):
        n = RandomNumber(5, tmin=5)
        self.assertEqual(n, 5)


class TestCompactIntList(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(CompactIntList([]), "")

    def test_single(self):
        self.assertEqual(CompactIntList([7]), "7")

    def test_range(self):
        self.assertEqual(CompactIntList([1, 2, 3, 4, 5]), "1-5")

    def test_two_ranges(self):
        self.assertEqual(CompactIntList([1, 2, 3, 7, 8]), "1-3 7-8")

    def test_gaps(self):
        self.assertEqual(CompactIntList([1, 3, 5]), "1 3 5")


class TestCountedCommandGenerator(unittest.TestCase):
    def test_nmax(self):
        ntasks = 10
        gen = CountedCommandGenerator(nmax=ntasks)
        count = 0
        while True:
            try:
                g = gen.next()
            except StopIteration:
                break
            self.assertIsNotNone(re.match(r"echo\s+\d+", g))
            count += 1
        self.assertEqual(count, ntasks)

    def test_custom_command(self):
        gen = CountedCommandGenerator(nmax=3, command="/bin/true")
        out = [gen.next() for _ in range(3)]
        self.assertTrue(all("/bin/true" in s for s in out))
        self.assertIn("0", out[0])
        self.assertIn("1", out[1])
        self.assertIn("2", out[2])

    def test_extra_kwargs_raise(self):
        with self.assertRaises(LauncherException):
            CountedCommandGenerator(nmax=5, invalid=1)


class TestSleepCommandGenerator(unittest.TestCase):
    def test_nmax_and_sleep_format(self):
        ntasks = 5
        tmax = 7
        gen = SleepCommandGenerator(nmax=ntasks, tmax=tmax)
        count = 0
        while True:
            try:
                g = gen.next()
            except StopIteration:
                break
            parts = g.split()
            # echo i 2>&1 > /dev/null ; sleep t
            self.assertEqual(parts[0], "echo")
            self.assertEqual(int(parts[1]), count)
            self.assertEqual(parts[5], ";")
            self.assertEqual(parts[6], "sleep")
            self.assertLessEqual(int(parts[7]), tmax)
            count += 1
        self.assertEqual(count, ntasks)

    def test_barrier_inserted(self):
        ntasks = 6
        barrier_interval = 2
        gen = SleepCommandGenerator(
            nmax=ntasks, tmax=3, barrier=barrier_interval
        )
        barriers = 0
        commands = 0
        while True:
            try:
                g = gen.next()
            except StopIteration:
                break
            if g == pylauncherBarrierString:
                barriers += 1
            else:
                commands += 1
        self.assertEqual(commands, ntasks)
        self.assertGreaterEqual(barriers, 1)


class TestSingleSleepCommand(unittest.TestCase):
    def test_returns_string(self):
        cmd = SingleSleepCommand(1, tmin=1)
        self.assertIsInstance(cmd, str)
        self.assertIn("sleep", cmd)
        self.assertIn("echo", cmd)


class TestCommandline(unittest.TestCase):
    def test_default_cores(self):
        c = Commandline("echo hello")
        self.assertEqual(c["command"], "echo hello")
        self.assertEqual(c["cores"], 1)

    def test_explicit_cores(self):
        c = Commandline("mpirun -n 4 ./a.out", cores=4)
        self.assertEqual(c["command"], "mpirun -n 4 ./a.out")
        self.assertEqual(c["cores"], 4)

    def test_str_repr(self):
        c = Commandline("foo", cores=2)
        s = str(c)
        self.assertIn("foo", s)
        self.assertIn("2", s)


class TestCommandlineGenerator(unittest.TestCase):
    def test_empty_list_requires_nmax_zero(self):
        with self.assertRaises(LauncherException):
            CommandlineGenerator(list=[])

    def test_cores_raises(self):
        with self.assertRaises(LauncherException):
            CommandlineGenerator(list=[Commandline("x")], cores=1)

    def test_iterate_list(self):
        clist = [
            Commandline("a", cores=1),
            Commandline("b", cores=2),
            Commandline("c", cores=1),
        ]
        gen = CommandlineGenerator(list=clist)
        self.assertEqual(len(gen), 3)
        c0 = gen.next()
        self.assertEqual(c0["command"], "a")
        self.assertEqual(c0["cores"], 1)
        c1 = gen.next()
        self.assertEqual(c1["command"], "b")
        self.assertEqual(c1["cores"], 2)
        c2 = gen.next()
        self.assertEqual(c2["command"], "c")
        self.assertTrue(gen.exhausted())

    def test_nmax_stop(self):
        clist = [Commandline("x", cores=1) for _ in range(5)]
        gen = CommandlineGenerator(list=clist, nmax=3)
        for _ in range(3):
            gen.next()
        self.assertTrue(gen.stopping())

    def test_abort(self):
        clist = [Commandline("x", cores=1)]
        gen = CommandlineGenerator(list=clist)
        gen.abort()
        self.assertTrue(gen.stopped)

    def test_finish(self):
        clist = [Commandline("x", cores=1)]
        gen = CommandlineGenerator(list=clist)
        gen.finish()
        self.assertTrue(gen._exhausted)


class TestListCommandlineGenerator(unittest.TestCase):
    def test_string_list_wrapped(self):
        gen = ListCommandlineGenerator(list=["cmd1", "cmd2", "cmd3"])
        self.assertEqual(len(gen), 3)
        c = gen.next()
        self.assertEqual(c["command"], "cmd1")
        self.assertEqual(c["cores"], 1)
        c = gen.next()
        self.assertEqual(c["command"], "cmd2")
        c = gen.next()
        self.assertEqual(c["command"], "cmd3")
        self.assertTrue(gen.exhausted())


class TestFileCommandlineGenerator(unittest.TestCase):
    def test_simple_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("line1\n")
            f.write("line2\n")
            f.write("line3\n")
            fn = f.name
        try:
            gen = FileCommandlineGenerator(fn, cores=1)
            self.assertEqual(gen.next()["command"], "line1")
            self.assertEqual(gen.next()["command"], "line2")
            self.assertEqual(gen.next()["command"], "line3")
            self.assertTrue(gen.exhausted())
        finally:
            os.unlink(fn)

    def test_skips_comments_and_blanks(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("# comment\n")
            f.write("\n")
            f.write("actual\n")
            fn = f.name
        try:
            gen = FileCommandlineGenerator(fn, cores=1)
            c = gen.next()
            self.assertEqual(c["command"], "actual")
            self.assertTrue(gen.exhausted())
        finally:
            os.unlink(fn)

    def test_cores_from_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("2,cmd_a\n")
            f.write("4,cmd_b\n")
            fn = f.name
        try:
            gen = FileCommandlineGenerator(fn, cores="file")
            c = gen.next()
            self.assertEqual(c["command"], "cmd_a")
            self.assertEqual(c["cores"], 2)
            c = gen.next()
            self.assertEqual(c["command"], "cmd_b")
            self.assertEqual(c["cores"], 4)
        finally:
            os.unlink(fn)

    def test_tid_substitute(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("echo PYL_ID\n")
            f.write("echo PYLTID\n")
            fn = f.name
        try:
            gen = FileCommandlineGenerator(fn, cores=1)
            c0 = gen.next()
            self.assertEqual(c0["command"], "echo 0")
            c1 = gen.next()
            self.assertEqual(c1["command"], "echo 1")
        finally:
            os.unlink(fn)

    def test_schedule_block(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("a\n")
            f.write("b\n")
            f.write("c\n")
            fn = f.name
        try:
            gen = FileCommandlineGenerator(fn, cores=1, schedule="block2")
            # block2: first two lines become one command "a && b", then "c"
            c0 = gen.next()
            self.assertIn("a", c0["command"])
            self.assertIn("b", c0["command"])
            self.assertIn("&&", c0["command"])
            c1 = gen.next()
            self.assertEqual(c1["command"], "c")
        finally:
            os.unlink(fn)

    def test_schedule_invalid_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("x\n")
            fn = f.name
        try:
            with self.assertRaises(LauncherException):
                FileCommandlineGenerator(fn, cores=1, schedule="invalid")
        finally:
            os.unlink(fn)


class TestDynamicCommandlineGenerator(unittest.TestCase):
    def test_nmax_raises(self):
        with self.assertRaises(LauncherException):
            DynamicCommandlineGenerator(list=[], nmax=5)

    def test_append_after_finish_raises(self):
        class WithCores(DynamicCommandlineGenerator):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.cores = 1

        gen = WithCores(list=[])
        gen.finish()
        with self.assertRaises(LauncherException):
            gen.append("echo foo")


class TestCompletion(unittest.TestCase):
    def test_base_completion_test_runtime(self):
        c = Completion(taskid=0, taskmaxruntime=0)
        self.assertFalse(c.test(0.0))
        # with taskmaxruntime and curtime > starttime + taskmaxruntime it would return True
        c2 = Completion(taskid=0, taskmaxruntime=1, starttime=0.0)
        # curtime must be > starttime + taskmaxruntime
        self.assertTrue(c2.test(2.0))

    def test_attach_default(self):
        c = Completion(taskid=0)
        self.assertEqual(c.attach("mycommand"), "mycommand")


class TestWrapCompletion(unittest.TestCase):
    def test_stampname(self):
        c = WrapCompletion(taskid=42, workdir="/tmp")
        self.assertEqual(c.stampname(), "/tmp/expire42")

    def test_successname(self):
        c = WrapCompletion(taskid=7, workdir="/tmp")
        self.assertEqual(c.successname(), "/tmp/success7")

    def test_attach_empty_command(self):
        c = WrapCompletion(taskid=1, workdir=".")
        out = c.attach("   ")
        self.assertIn("touch", out)
        self.assertIn("expire1", out)

    def test_attach_non_empty(self):
        c = WrapCompletion(taskid=2, workdir=".")
        out = c.attach("echo hello")
        self.assertIn("echo hello", out)
        self.assertIn("touch", out)
        self.assertIn("success2", out)
        self.assertIn("expire2", out)


class TestBareCompletion(unittest.TestCase):
    def test_stampname(self):
        c = BareCompletion(taskid=3, workdir="/tmp")
        self.assertEqual(c.stampname(), "/tmp/expire3")


class TestNode(unittest.TestCase):
    def test_create_and_occupy_release(self):
        h = {"host": "foo", "hostnum": 0, "task_loc": 0, "phys_core": "0"}
        n = Node(h, nodeid=0)
        self.assertTrue(n.isfree())
        self.assertEqual(n.nodestring(), "X")
        n.occupyWithTask(13)
        self.assertFalse(n.isfree())
        self.assertEqual(n.nodestring(), "13")
        n.release()
        self.assertTrue(n.isfree())
        self.assertEqual(n.taskid, -1)

    def test_release_free_raises(self):
        h = {"host": "x", "hostnum": 0, "task_loc": 0, "phys_core": "0"}
        n = Node(h, nodeid=0)
        with self.assertRaises(LauncherException):
            n.release()


class TestHostLocator(unittest.TestCase):
    def test_len_and_firsthost(self):
        # Need a minimal pool to get a locator
        pool = LocalHostPool(nhosts=4)
        loc = pool.request_nodes(2)
        self.assertIsNotNone(loc)
        self.assertEqual(len(loc), 2)
        host = loc.firsthost()
        self.assertIsInstance(host, str)
        self.assertTrue(len(host) > 0)
        pool.release()


class TestHostPool(unittest.TestCase):
    def test_local_nhosts(self):
        pool = LocalHostPool(nhosts=5)
        self.assertEqual(len(pool), 5)
        pool.release()

    def test_request_and_occupy_release(self):
        pool = LocalHostPool(nhosts=4)
        loc = pool.request_nodes(2)
        self.assertIsNotNone(loc)
        self.assertEqual(len(loc), 2)
        pool.occupyNodes(loc, taskid=99)
        self.assertIsNone(pool.request_nodes(4))
        self.assertFalse(pool[0].isfree())
        self.assertTrue(pool[2].isfree())
        pool.releaseNodesByTask(99)
        loc2 = pool.request_nodes(4)
        self.assertIsNotNone(loc2)
        self.assertEqual(len(loc2), 4)
        pool.release()

    def test_hosts_subset(self):
        pool = LocalHostPool(nhosts=5)
        nodes = pool.hosts([0, 2, 4])
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[0].nodeid, 0)
        self.assertEqual(nodes[1].nodeid, 2)
        self.assertEqual(nodes[2].nodeid, 4)
        pool.release()


class TestFileCommandlineGeneratorCorelineSplit(unittest.TestCase):
    def test_valid_line(self):
        gen = FileCommandlineGenerator.__new__(FileCommandlineGenerator)
        gen.schedule = "default"
        cores, line = gen.coreline_split("4,mycommand")
        self.assertEqual(cores, 4)
        self.assertEqual(line, "mycommand")

    def test_invalid_line_raises(self):
        gen = FileCommandlineGenerator.__new__(FileCommandlineGenerator)
        gen.schedule = "default"
        with self.assertRaises(LauncherException):
            gen.coreline_split("nocomma")


if __name__ == "__main__":
    unittest.main()
