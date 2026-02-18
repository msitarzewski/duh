import { CalibrationDashboard } from '@/components/calibration'
import { PageTransition } from '@/components/shared'

export function CalibrationPage() {
  return (
    <PageTransition>
      <div className="p-6">
        <CalibrationDashboard />
      </div>
    </PageTransition>
  )
}
