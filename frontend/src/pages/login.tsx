export default function LoginPage() {
  const handleLogin = () => {
    window.location.href = '/api/auth/google/login';
  };

  return (
    <div className="flex min-h-screen items-center justify-center dark:bg-dark-bg">
      <div className="w-full max-w-sm space-y-6 text-center">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Helpey</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Sign in to chat with your Google Drive files.
        </p>
        <button
          onClick={handleLogin}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-dark transition-colors"
        >
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
