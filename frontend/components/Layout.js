import ThemeToggle from './ThemeToggle';
import InstallPrompt from './InstallPrompt';
import AssistantChatWidget from './AssistantChatWidget';

export default function Layout({ children, theme, setTheme }) {
  return (
    <div className="min-h-screen flex flex-col p-4 relative">
      <header className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Operator Dashboard</h1>
        <ThemeToggle theme={theme} setTheme={setTheme} />
      </header>
      <main className="flex-1 grid gap-4">{children}</main>
      <footer className="text-center text-sm mt-4 opacity-75">
        Powered by FastAPI
      </footer>
      <AssistantChatWidget />
      <InstallPrompt />
    </div>
  );
}
