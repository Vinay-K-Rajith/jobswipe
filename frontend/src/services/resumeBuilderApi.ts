import api from './api';

export const previewResume = (
  studentId: string,
  templateId: string,
  resumeText?: string,
  instruction?: string
) =>
  api.post<{ resume_text: string }>('/resume-builder/preview', {
    student_id: studentId,
    template_id: templateId,
    resume_text: resumeText ?? null,
    instruction: instruction ?? null,
  });

export const downloadResume = async (studentId: string, resumeText: string) => {
  const response = await api.post(
    '/resume-builder/download',
    { student_id: studentId, resume_text: resumeText },
    { responseType: 'blob' }
  );
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `resume_${studentId}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
