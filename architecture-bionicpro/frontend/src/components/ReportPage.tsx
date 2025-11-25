import React, { useState, useRef, useEffect } from 'react';
// Импортируем useRef и useEffect
import { useKeycloak } from '@react-keycloak/web';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<any | null>(null);

  // 1. Создаем ссылку на DOM-элемент
  const reportEndRef = useRef<HTMLDivElement>(null);

  // 2. Функция для автоматической прокрутки вниз
  const scrollToBottom = () => {
    reportEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // 3. Используем useEffect для вызова прокрутки при обновлении reportData
  useEffect(() => {
    if (reportData) {
      scrollToBottom();
    }
  }, [reportData]); // Запускается при каждом изменении reportData


  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }
    // ... (остальная часть функции downloadReport остается без изменений)
    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Accept': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setReportData(data);
      } else {
        const errorBody = await response.text();
        setError(`Failed to download report: ${response.status} - ${errorBody}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // ... (остальная часть логики аутентификации остается без изменений)
  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reportData && (
          // 4. Добавляем классы Tailwind CSS для ограничения высоты и ручной прокрутки
          // (max-h-60 делает окно не выше 15rem, overflow-y-auto добавляет полосу прокрутки)
          <div className="mt-4 p-4 bg-green-100 text-green-700 rounded max-h-60 overflow-y-auto">
            <h3 className="font-semibold">Report Data:</h3>
            <pre className="whitespace-pre-wrap break-all text-sm">
              {JSON.stringify(reportData, null, 2)}
            </pre>
            {/* 5. Добавляем невидимый элемент в конец, на который ссылаемся */}
            <div ref={reportEndRef} />
          </div>
        )}

      </div>
    </div>
  );
};

export default ReportPage;
