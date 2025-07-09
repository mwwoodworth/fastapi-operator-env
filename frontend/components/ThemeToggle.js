export default function ThemeToggle({ theme, setTheme }) {
  return (
    <button
      className="px-3 py-1 border rounded"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
    >
      {theme === 'dark' ? 'Light' : 'Dark'} Mode
    </button>
  );
}
