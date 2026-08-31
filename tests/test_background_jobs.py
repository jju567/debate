import unittest
import time
from background_jobs import start_background_job, get_job_status, list_background_jobs
from tool_executor import execute_tool_call

class TestBackgroundJobs(unittest.TestCase):
    def test_start_and_get_job_status(self):
        code = "import time\nprint('aloitetaan')\ntime.sleep(0.2)\nprint('valmis_123')"
        res = start_background_job(code, name="testi_simulaatio")
        self.assertTrue(res["success"])
        job_id = res["job_id"]

        # Odotetaan hetki suoritusta
        time.sleep(0.8)
        status = get_job_status(job_id)
        self.assertTrue(status["success"])
        self.assertIn(status["status"], ["running", "completed"])
        self.assertIn("aloitetaan", status["recent_logs"])

    def test_tool_executor_background_job(self):
        msg, raw = execute_tool_call("start_background_job", {"code": "print('taustatyö_ok')", "name": "unit_test_job"})
        self.assertIn("Taustalaskenta käynnistetty", msg)
        self.assertIn("job_", raw)

        # Tarkistetaan listaustyökalu
        msg_list, raw_list = execute_tool_call("list_background_jobs", {})
        self.assertIn("unit_test_job", msg_list)

if __name__ == "__main__":
    unittest.main()
