export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = '/api/auth/google/login';
  };

  const handleSSOLogin = () => {
    window.location.href = '/api/auth/workos/login';
  };

  return (
    <div className="flex min-h-screen items-center justify-center dark:bg-dark-bg">
      <div className="w-full max-w-sm space-y-6 text-center">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Helpey</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Sign in to chat with your Google Drive files.
        </p>
        <div className="space-y-3">
          <button
            onClick={handleGoogleLogin}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-dark transition-colors"
          >
            Sign in with Google
          </button>
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300 dark:border-gray-600" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-background px-2 text-gray-500 dark:bg-dark-bg dark:text-gray-400">
                or
              </span>
            </div>
          </div>
          <button
            onClick={handleSSOLogin}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors dark:border-gray-600 dark:bg-dark-card dark:text-gray-200 dark:hover:bg-dark-hover"
          >
            Sign in with SSO
          </button>
        </div>
      </div>
    </div>
  );
}
