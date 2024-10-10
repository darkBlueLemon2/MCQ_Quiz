import streamlit as st
import pandas as pd
import json
import os

def load_questions(file):
    df = pd.read_csv(file)
    questions = df.to_dict('records')
    for q in questions:
        q['options'] = q['options'].split('|')
    return questions

def save_progress(progress, filename):
    progress_filename = f"data/{filename}_progress.json"
    with open(progress_filename, 'w') as f:
        json.dump(progress, f)

def load_progress(filename):
    progress_filename = f"data/{filename}_progress.json"
    if os.path.exists(progress_filename):
        with open(progress_filename, 'r') as f:
            return json.load(f)
    return {}

def list_csv_files(directory):
    return [f for f in os.listdir(directory) if f.endswith('.csv')]

def find_first_unanswered_question(progress, total_questions):
    for i in range(total_questions):
        if str(i) not in progress:
            return i
    return total_questions

def display_quiz(file_path):
    questions = load_questions(file_path)
    filename = os.path.splitext(os.path.basename(file_path))[0]
    progress = load_progress(filename)

    if 'current_question' not in st.session_state:
        st.session_state.current_question = find_first_unanswered_question(progress, len(questions))

    if st.session_state.current_question < len(questions):
        question = questions[st.session_state.current_question]
        st.markdown(f"### Question {question['question_number']}")
        st.write(question['question'])

        current_progress = progress.get(str(st.session_state.current_question), {})
        if current_progress:
            selected_option = current_progress['selected']
            selected_index = question['options'].index(selected_option) if selected_option in question['options'] else None
        else:
            selected_index = None

        selected_option = st.radio("Choose an option:", question['options'], key=f"q{st.session_state.current_question}", index=selected_index)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="previous_button"):
                st.session_state.current_question = max(0, st.session_state.current_question - 1)
                st.experimental_rerun()
        with col2:
            if st.button("Next", key="next_button"):
                progress[str(st.session_state.current_question)] = {
                    'selected': selected_option,
                }
                save_progress(progress, filename)
                st.session_state.current_question += 1
                st.experimental_rerun()
    else:
        # st.success("Quiz completed!")

        # Calculate the score
        correct_answers = 0
        total_questions = len(questions)

        for i, (q, result) in enumerate(progress.items()):
            question = questions[int(q)]
            if result['selected'] == question['correct_option']:
                correct_answers += 1

        # Display the score
        st.markdown(f"### Your score: {correct_answers}/{total_questions}")

        # Show only the questions that were answered incorrectly
        incorrect_questions = [
            (questions[int(q)], result)
            for q, result in progress.items()
            if result['selected'] != questions[int(q)]['correct_option']
        ]

        if incorrect_questions:
            st.markdown("---")
            st.subheader("Review Incorrect Answers:")
            for question, result in incorrect_questions:
                st.markdown(f"#### Question {question['question_number']}")
                st.write(question['question'])
                st.write("Options:")
                for option in question['options']:
                    st.write(f"- {option}")
                st.warning(f"Your answer: {result['selected']}")
                st.success(f"Correct answer: {question['correct_option']}")
                st.markdown("---")

        if st.button("Restart Quiz", key="restart_button"):
            st.session_state.current_question = 0
            progress_filename = f"data/{filename}_progress.json"
            if os.path.exists(progress_filename):
                os.remove(progress_filename)
            st.experimental_rerun()

def main():
    st.set_page_config(page_title="Multiple Choice Quiz App", page_icon=":question:", layout="wide")
    st.title("Multiple Choice Quiz")

    # List CSV files in the data/ directory
    csv_files = list_csv_files('data')

    if not csv_files:
        st.error("No CSV files found in the 'data/' directory.")
        return

    # Use session state to store the selected file and whether the quiz has started
    if 'selected_file' not in st.session_state:
        st.session_state.selected_file = None

    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False

    # If the quiz hasn't started yet, display the selectbox and start button
    if not st.session_state.quiz_started:
        st.session_state.selected_file = st.selectbox("Choose a CSV file", [""] + csv_files)

        if st.session_state.selected_file:
            file_path = os.path.join('data', st.session_state.selected_file)

            if st.button("Start Quiz", key="start_button"):
                st.session_state.quiz_started = True
                st.experimental_rerun()  # Rerun the app to reflect the state change immediately

    # Once the quiz has started, don't show the CSV list or Start Quiz button
    if st.session_state.quiz_started:
        file_path = os.path.join('data', st.session_state.selected_file)
        display_quiz(file_path)

if __name__ == "__main__":
    main()