import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-700">404</h1>
        <p className="text-xl text-gray-400 mt-4">Page not found</p>
        <Link to="/dashboard" className="inline-block mt-6 px-6 py-2 bg-blue-600 rounded-lg text-sm hover:bg-blue-700">
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
