// Input HH:MM:SS. Hanya menerima angka, ":" dan "." lalu merapikan saat blur.
import { formatTimecode, parseTimecode } from "../utils/time.js";

export default function TimeInput({ value, onChange, invalid, disabled }) {
  const handleChange = (e) => onChange(e.target.value.replace(/[^0-9:.,]/g, "").slice(0, 12));
  const handleBlur = () => {
    const sec = parseTimecode(value);
    if (sec !== null && !value.includes(".")) onChange(formatTimecode(sec));
  };
  return (
    <input
      className={`input font-mono ${invalid ? "input-error" : ""}`}
      inputMode="numeric"
      placeholder="00:00:00"
      value={value}
      onChange={handleChange}
      onBlur={handleBlur}
      disabled={disabled}
      spellCheck={false}
    />
  );
}
