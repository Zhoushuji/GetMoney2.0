import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type TaskState = {
  taskId?: string;
  setTaskId: (taskId?: string) => void;
};

export const useTaskStore = create<TaskState>()(
  persist(
    (set) => ({
      taskId: undefined,
      setTaskId: (taskId?: string) => set({ taskId }),
    }),
    {
      name: 'leadgen-active-task',
      partialize: (state) => ({ taskId: state.taskId }),
    },
  ),
);
