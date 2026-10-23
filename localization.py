"""Greek messages and an idempotent translation of known fictional demo records."""
import re

DEMO_TEXT = {'Alex Morgan': 'Αλέξανδρος Δημητρίου',
 'Jamie Parker': 'Γιάννης Παπαδόπουλος',
 'Sofia Lewis': 'Σοφία Λέκκα',
 'Daniel Chen': 'Δημήτρης Παππάς',
 'Emma Wilson': 'Έλενα Αντωνίου',
 'Noah Bennett': 'Νίκος Βασιλείου',
 'Jamie': 'Γιάννης',
 'Taylor': 'Μαρία',
 'Get stronger. Move better. Stay consistent.': 'Περισσότερη δύναμη. Καλύτερη κίνηση. Σταθερή συνέπεια.',
 'Build a consistent squat pattern and make time for mobility.': 'Βελτίωση τεχνικής στα καθίσματα και '
                                                                 'περισσότερος χρόνος για κινητικότητα.',
 'Build confidence with free weights.': 'Περισσότερη αυτοπεποίθηση με τα ελεύθερα βάρη.',
 'Upper-body strength': 'Δύναμη στον άνω κορμό',
 'Improve conditioning.': 'Βελτίωση φυσικής κατάστασης.',
 'Steady, sustainable progress': 'Σταθερή, βιώσιμη πρόοδος',
 'Train three times each week.': 'Τρεις προπονήσεις κάθε εβδομάδα.',
 'Full-body strength': 'Δύναμη σε όλο το σώμα',
 'Move well and feel stronger.': 'Καλύτερη κίνηση και περισσότερη δύναμη.',
 'Mobility and consistency': 'Κινητικότητα και συνέπεια',
 'Full body foundations': 'Βάσεις δύναμης για όλο το σώμα',
 'Engine room': 'Χτίσιμο αντοχής',
 'Strong & steady': 'Δύναμη και σταθερότητα',
 'Move & reset': 'Κίνηση και αποφόρτιση',
 'A little stronger, together. Build confidence with the essential movement patterns.': 'Λίγο πιο δυνατοί, '
                                                                                        'μαζί. Χτίσε '
                                                                                        'αυτοπεποίθηση στις '
                                                                                        'βασικές κινήσεις.',
 'Find your pace with a coach-led mix of cardio and functional strength.': 'Βρες τον ρυθμό σου με αερόβια '
                                                                           'άσκηση και λειτουργική '
                                                                           'ενδυνάμωση, με καθοδήγηση '
                                                                           'προπονητή.',
 'A balanced session of strength work and conditioning. All levels welcome.': 'Ισορροπημένη προπόνηση '
                                                                              'δύναμης και φυσικής '
                                                                              'κατάστασης. Για όλα τα '
                                                                              'επίπεδα.',
 'Create space to move. A slower session focused on control, mobility, and recovery.': 'Δώσε χώρο στην '
                                                                                       'κίνηση. Ήπια '
                                                                                       'προπόνηση με έμφαση '
                                                                                       'στον έλεγχο, την '
                                                                                       'κινητικότητα και την '
                                                                                       'αποκατάσταση.',
 '6 min easy row\nHip openers + band pull-aparts\n2 rounds of bodyweight squats': '6 λεπτά χαλαρή '
                                                                                  'κωπηλατική\n'
                                                                                  'Κινητικότητα ισχίων και '
                                                                                  'ανοίγματα με λάστιχο\n'
                                                                                  '2 γύροι καθισμάτων χωρίς '
                                                                                  'βάρος',
 'Back squat · 4 × 6\nDumbbell bench press · 3 × 10\nSingle-arm row · 3 × 10 each side': 'Κάθισμα με μπάρα · '
                                                                                         '4 × 6\n'
                                                                                         'Πιέσεις στήθους με '
                                                                                         'αλτήρες · 3 × 10\n'
                                                                                         'Κωπηλατική με έναν '
                                                                                         'αλτήρα · 3 × 10 '
                                                                                         'ανά πλευρά',
 '8-minute partner circuit\n10 kettlebell swings + 8 box step-ups\nEasy stretch to finish': '8 λεπτά κυκλική '
                                                                                            'προπόνηση σε '
                                                                                            'ζευγάρια\n'
                                                                                            '10 αιωρήσεις '
                                                                                            'δράμι και 8 '
                                                                                            'ανεβάσματα σε '
                                                                                            'κουτί\n'
                                                                                            'Ήπιες διατάσεις '
                                                                                            'στο τέλος',
 '5 min bike\nDynamic lunges + shoulder circles': '5 λεπτά ποδήλατο\nΔυναμικές προβολές και κύκλοι ώμων',
 '4 rounds at a steady pace\n400 m row · 12 wall balls\n10 alternating dumbbell snatches\nRest 90 seconds between rounds': '4 '
                                                                                                                           'γύροι '
                                                                                                                           'σε '
                                                                                                                           'σταθερό '
                                                                                                                           'ρυθμό\n'
                                                                                                                           '400 '
                                                                                                                           'μ. '
                                                                                                                           'κωπηλατική '
                                                                                                                           '· '
                                                                                                                           '12 '
                                                                                                                           'ρίψεις '
                                                                                                                           'μπάλας '
                                                                                                                           'στον '
                                                                                                                           'τοίχο\n'
                                                                                                                           '10 '
                                                                                                                           'εναλλάξ '
                                                                                                                           'αρασέ '
                                                                                                                           'με '
                                                                                                                           'αλτήρα\n'
                                                                                                                           '90 '
                                                                                                                           'δευτερόλεπτα '
                                                                                                                           'διάλειμμα '
                                                                                                                           'ανάμεσα '
                                                                                                                           'στους '
                                                                                                                           'γύρους',
 '6 min alternating bike / farmer carry\nSlow breathing and calf stretch': '6 λεπτά εναλλάξ ποδήλατο και '
                                                                           'περπάτημα με βάρη\n'
                                                                           'Ήρεμες αναπνοές και διάταση '
                                                                           'γαστροκνημίων',
 '5 min ski erg\nGlute bridges + dead bugs': '5 λεπτά εργόμετρο σκι\n'
                                             'Γέφυρες γλουτών και εναλλάξ εκτάσεις άκρων σε ύπτια θέση',
 'Deadlift · 4 × 5\nSplit squat · 3 × 8 each side\nAssisted pull-up · 3 × 8': 'Άρση θανάτου · 4 × 5\n'
                                                                              'Στατικό κάθισμα σε προβολή · '
                                                                              '3 × 8 ανά πλευρά\n'
                                                                              'Έλξεις με υποβοήθηση · 3 × 8',
 '10 min easy-paced circuit\nSled push + farmer carry\nHip flexor stretch': '10 λεπτά ήπια κυκλική '
                                                                            'προπόνηση\n'
                                                                            'Σπρώξιμο ελκήθρου και περπάτημα '
                                                                            'με βάρη\n'
                                                                            'Διάταση καμπτήρων ισχίου',
 '5 min gentle flow\nControlled joint circles': '5 λεπτά ήπια συνεχόμενη κίνηση\n'
                                                'Ελεγχόμενοι κύκλοι αρθρώσεων',
 '90/90 hip transitions · 3 × 8\nThoracic rotations · 3 × 8\nTempo goblet squat · 3 × 6\nShoulder mobility flow · 8 min': 'Εναλλαγές '
                                                                                                                          'ισχίων '
                                                                                                                          '90/90 '
                                                                                                                          '· '
                                                                                                                          '3 '
                                                                                                                          '× '
                                                                                                                          '8\n'
                                                                                                                          'Στροφές '
                                                                                                                          'θωρακικής '
                                                                                                                          'μοίρας '
                                                                                                                          '· '
                                                                                                                          '3 '
                                                                                                                          '× '
                                                                                                                          '8\n'
                                                                                                                          'Κάθισμα '
                                                                                                                          'με '
                                                                                                                          'βάρος '
                                                                                                                          'μπροστά '
                                                                                                                          'σε '
                                                                                                                          'αργό '
                                                                                                                          'ρυθμό '
                                                                                                                          '· '
                                                                                                                          '3 '
                                                                                                                          '× '
                                                                                                                          '6\n'
                                                                                                                          'Κινητικότητα '
                                                                                                                          'ώμων '
                                                                                                                          '· '
                                                                                                                          '8 '
                                                                                                                          'λεπτά',
 'Guided full-body stretch\n3 min relaxed breathing': 'Καθοδηγούμενες διατάσεις όλου του σώματος\n'
                                                      '3 λεπτά ήρεμες αναπνοές',
 'Body weight': 'Σωματικό βάρος',
 'Back squat': 'Κάθισμα με μπάρα',
 'Morning check-in': 'Πρωινή καταγραφή',
 'Controlled reps. Feeling stronger.': 'Ελεγχόμενες επαναλήψεις. Αισθάνομαι πιο δυνατός.',
 'Feeling good after this week’s sessions.': 'Αισθάνομαι καλά μετά τις προπονήσεις της εβδομάδας.'}

ERRORS = {'Please sign in to continue.': 'Συνδέσου για να συνεχίσεις.',
 'This area is for the studio owner.': 'Αυτός ο χώρος είναι για τον ιδιοκτήτη.',
 'Your session expired. Refresh the page and try again.': 'Η σύνδεσή σου έληξε. Ανανέωσε τη σελίδα και '
                                                          'δοκίμασε ξανά.',
 'Please check the information you entered.': 'Έλεγξε τα στοιχεία που συμπλήρωσες.',
 'That request is too large.': 'Το αίτημα είναι πολύ μεγάλο.',
 'Please enter valid form data.': 'Συμπλήρωσε έγκυρα στοιχεία στη φόρμα.',
 'Too many attempts. Please try again in five minutes.': 'Έγιναν πολλές προσπάθειες. Δοκίμασε ξανά σε πέντε '
                                                         'λεπτά.',
 'Email or password is incorrect.': 'Το email ή ο κωδικός δεν είναι σωστός.',
 'Demo access is disabled.': 'Η δοκιμαστική πρόσβαση είναι απενεργοποιημένη.',
 'Choose a valid month.': 'Διάλεξε έναν έγκυρο μήνα.',
 'Use a client account to book a class.': 'Χρησιμοποίησε λογαριασμό μέλους για να κλείσεις μάθημα.',
 'This class is no longer available.': 'Αυτό το μάθημα δεν είναι πλέον διαθέσιμο.',
 'This class has already started.': 'Το μάθημα έχει ήδη ξεκινήσει.',
 'Your membership does not include this month. Contact your coach.': 'Η συνδρομή σου δεν καλύπτει αυτόν τον '
                                                                     'μήνα. Επικοινώνησε με τον προπονητή '
                                                                     'σου.',
 'You already have a place in this class.': 'Έχεις ήδη θέση σε αυτό το μάθημα.',
 'This class is full. Try another time.': 'Το μάθημα είναι πλήρες. Δοκίμασε άλλη ώρα.',
 'You have another class at this time.': 'Έχεις άλλο μάθημα την ίδια ώρα.',
 'Booking not found.': 'Η κράτηση δεν βρέθηκε.',
 'You can only cancel a class before it starts.': 'Μπορείς να ακυρώσεις μόνο πριν από την έναρξη του '
                                                  'μαθήματος.',
 'Progress entries cannot be dated in the future.': 'Οι καταγραφές προόδου δεν μπορούν να έχουν μελλοντική '
                                                    'ημερομηνία.',
 'Choose body weight or an exercise.': 'Διάλεξε σωματικό βάρος ή άσκηση.',
 'Entry not found.': 'Η καταγραφή δεν βρέθηκε.',
 'Your current password is incorrect.': 'Ο τρέχων κωδικός δεν είναι σωστός.',
 'Enter a valid email address.': 'Συμπλήρωσε μια έγκυρη διεύθυνση email.',
 'A member with that email already exists.': 'Υπάρχει ήδη μέλος με αυτό το email.',
 'Member not found.': 'Το μέλος δεν βρέθηκε.',
 'Schedule classes in the future.': 'Όρισε το μάθημα σε μελλοντική ημερομηνία και ώρα.',
 'Choose a valid class category.': 'Διάλεξε έγκυρο είδος προπόνησης.',
 'Class not found.': 'Το μάθημα δεν βρέθηκε.',
 'A booked class cannot be rescheduled. Cancel it and create a new class.': 'Δεν μπορεί να αλλάξει ώρα ένα '
                                                                            'μάθημα με κρατήσεις. Ακύρωσέ το '
                                                                            'και δημιούργησε νέο.',
 'Choose an attendance status.': 'Διάλεξε κατάσταση παρουσίας.',
 'Attendance can be marked after a class starts.': 'Η παρουσία καταχωρίζεται μετά την έναρξη του μαθήματος.'}

FIELD_LABELS = {'name': 'Όνομα',
 'email': 'Email',
 'password': 'Κωδικός',
 'new_password': 'Νέος κωδικός',
 'class_id': 'Μάθημα',
 'logged_on': 'Ημερομηνία',
 'exercise': 'Άσκηση',
 'weight': 'Βάρος',
 'reps': 'Επαναλήψεις',
 'note': 'Σημείωση',
 'goal': 'Στόχος',
 'priority': 'Προτεραιότητα',
 'month': 'Μήνας',
 'months': 'Αριθμός μηνών',
 'weekly_limit': 'Εβδομαδιαίο όριο',
 'title': 'Τίτλος',
 'starts_at': 'Ημερομηνία και ώρα',
 'capacity': 'Θέσεις',
 'duration': 'Διάρκεια',
 'category': 'Είδος προπόνησης',
 'coach': 'Προπονητής',
 'description': 'Περιγραφή',
 'warmup': 'Προθέρμανση',
 'main': 'Κυρίως πρόγραμμα',
 'finisher': 'Τελικό μέρος'}

def field_label(key):
    return FIELD_LABELS.get(key, 'Στοιχείο')


def error_message(message):
    if message in ERRORS:
        return ERRORS[message]
    match = re.fullmatch(r'You have used your (\d+) bookings for this week and month\.', message)
    if match:
        return f'Έχεις χρησιμοποιήσει τις {match[1]} κρατήσεις σου για αυτή την εβδομάδα και τον μήνα.'
    match = re.fullmatch(r'There are already (\d+) bookings\. Capacity cannot be lower\.', message)
    if match:
        return f'Υπάρχουν ήδη {match[1]} κρατήσεις. Οι θέσεις δεν μπορούν να είναι λιγότερες.'
    if re.search('[Α-Ωα-ωάέήίόύώ]', message):
        return message
    return 'Έλεγξε τα στοιχεία, την ημερομηνία και την ώρα που συμπλήρωσες.'


def localize_demo(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    if connection.execute("SELECT 1 FROM app_settings WHERE key='demo_locale' AND value='el-v1'").fetchone():
        return
    # Translate only unchanged, known sample values. User-written values remain intact.
    for column in ('name', 'goal', 'priority'):
        for original, translated in DEMO_TEXT.items():
            connection.execute(f'UPDATE users SET {column}=? WHERE is_demo=1 AND {column}=?', (translated, original))
    demo_titles = ['Full body foundations', 'Engine room', 'Strong & steady', 'Move & reset']
    marks = ','.join('?' for _ in demo_titles)
    rows = connection.execute(f'SELECT * FROM classes WHERE title IN ({marks})', demo_titles).fetchall()
    for row in rows:
        if row['description'] not in DEMO_TEXT:
            continue
        fields = ('title', 'coach', 'description', 'warmup', 'main', 'finisher')
        values = [DEMO_TEXT.get(row[key], row[key]) for key in fields]
        connection.execute('UPDATE classes SET title=?,coach=?,description=?,warmup=?,main=?,finisher=? WHERE id=?', (*values, row['id']))
    for column in ('exercise', 'note'):
        for original, translated in DEMO_TEXT.items():
            connection.execute(f'UPDATE progress SET {column}=? WHERE user_id IN (SELECT id FROM users WHERE is_demo=1) AND {column}=?', (translated, original))
    connection.execute("INSERT INTO app_settings(key,value) VALUES('demo_locale','el-v1') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    connection.commit()
