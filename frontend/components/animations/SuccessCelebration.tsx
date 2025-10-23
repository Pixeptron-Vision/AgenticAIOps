// components/animations/SuccessCelebration.tsx
import { motion } from 'framer-motion';
import { Sparkles, CheckCircle, Zap } from 'lucide-react';
import confetti from 'canvas-confetti';
import { useEffect } from 'react';

export function SuccessCelebration({ message, onComplete }: { message?: string; onComplete: () => void }) {
  useEffect(() => {
    // Trigger confetti
    confetti({
      particleCount: 100,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#10b981', '#3b82f6', '#8b5cf6', '#ec4899'],
    });

    // Auto-close after 3 seconds
    const timer = setTimeout(onComplete, 3000);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.5 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm"
    >
      <motion.div
        initial={{ y: 50 }}
        animate={{ y: 0 }}
        className="bg-white rounded-2xl p-8 shadow-2xl text-center max-w-md"
      >
        <motion.div
          animate={{
            rotate: [0, 360],
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 0.6,
            ease: 'easeOut',
          }}
          className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full flex items-center justify-center shadow-lg"
        >
          <CheckCircle className="w-10 h-10 text-white" />
        </motion.div>

        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          🎉 Success!
        </h2>
        <p className="text-gray-600 mb-4">{message}</p>

        <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
          <Sparkles className="w-4 h-4" />
          <span>Model ready for deployment</span>
        </div>
      </motion.div>
    </motion.div>
  );
}