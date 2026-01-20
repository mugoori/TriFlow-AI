import { useAppStore } from '../store/appStore';

const steps = [
  { id: 'input', label: '제품 정보 입력', icon: '1' },
  { id: 'search', label: '유사 제품 검색', icon: '2' },
  { id: 'prompt', label: '프롬프트 생성', icon: '3' },
  { id: 'result', label: '결과 확인', icon: '4' },
] as const;

export default function StepIndicator() {
  const { currentStep, setCurrentStep } = useAppStore();

  const currentIndex = steps.findIndex((s) => s.id === currentStep);

  return (
    <div className="mb-8">
      <div className="flex items-center justify-center">
        {steps.map((step, index) => {
          const isActive = step.id === currentStep;
          const isCompleted = index < currentIndex;
          const isClickable = index <= currentIndex;

          return (
            <div key={step.id} className="flex items-center">
              <button
                onClick={() => isClickable && setCurrentStep(step.id)}
                disabled={!isClickable}
                className={`
                  flex items-center gap-2 px-4 py-2 rounded-full transition-all duration-200
                  ${isActive
                    ? 'bg-primary-600 text-white shadow-lg'
                    : isCompleted
                    ? 'bg-primary-100 text-primary-700 hover:bg-primary-200 cursor-pointer'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  }
                `}
              >
                <span
                  className={`
                    w-6 h-6 rounded-full flex items-center justify-center text-sm font-medium
                    ${isActive
                      ? 'bg-white text-primary-600'
                      : isCompleted
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-300 text-gray-500'
                    }
                  `}
                >
                  {isCompleted ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    step.icon
                  )}
                </span>
                <span className="text-sm font-medium hidden sm:inline">{step.label}</span>
              </button>

              {index < steps.length - 1 && (
                <div
                  className={`
                    w-8 md:w-16 h-0.5 mx-1
                    ${index < currentIndex ? 'bg-primary-400' : 'bg-gray-200'}
                  `}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
