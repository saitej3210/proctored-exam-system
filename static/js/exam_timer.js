console.log("⏳ exam_timer.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const box = document.getElementById("examTimerBox");
  const text = document.getElementById("examTimer");

  if (!box || !text) {
    console.error("❌ Timer DOM not found");
    return;
  }

  async function fetchTimer() {
    try {
      const res = await fetch(`/student/exam-timer?exam_id=${EXAM_ID}`);
      const data = await res.json();

      console.log("⏱ TIMER DATA:", data);

      if (!data.enabled || data.remaining_seconds == null) {
        box.style.display = "none";
        return;
      }

      let remaining = data.remaining_seconds;
      box.style.display = "block";

      updateUI(remaining);

      if (window.__examTimerInterval) {
        clearInterval(window.__examTimerInterval);
      }

      window.__examTimerInterval = setInterval(() => {
        remaining--;

        if (remaining <= 0) {
          clearInterval(window.__examTimerInterval);
          alert("⏰ Time Up! Exam will be submitted.");
          document.querySelector("form")?.submit();
          return;
        }

        updateUI(remaining);
      }, 1000);

    } catch (err) {
      console.error("❌ TIMER ERROR", err);
    }
  }

  function updateUI(sec) {
    const m = Math.floor(sec / 60).toString().padStart(2, "0");
    const s = (sec % 60).toString().padStart(2, "0");
    text.textContent = `${m}:${s}`;
  }

  fetchTimer();
});