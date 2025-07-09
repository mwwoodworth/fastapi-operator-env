import AuthGuard from '../../components/AuthGuard';
import CopilotApp from '../../components/CopilotApp';

export default function Page() {
  return (
    <AuthGuard>
      <div className="h-screen flex flex-col">
        <CopilotApp />
      </div>
    </AuthGuard>
  );
}
