# -*- coding: utf-8 -*-


from sklearn.metrics import f1_score
import numpy as np
from transformers import ElectraTokenizer
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MultiLabelBinarizer
from torch.nn import BCEWithLogitsLoss
import json
from transformers import ElectraForSequenceClassification, ElectraModel
from torch.optim import Adam
from sklearn.metrics import f1_score
from transformers import AutoModel, AutoTokenizer


# Initialize KO-ELECTRA tokenizer
# tokenizer = ElectraTokenizer.from_pretrained("monologg/koelectra-base-v3-discriminator")
tokenizer = AutoTokenizer.from_pretrained("beomi/KcELECTRA-base")
# Hyperparameters
vocab_size = tokenizer.vocab_size
embedding_dim = 768  # This should match the dimensionality of your word vectors
max_seq_length = 218
batch_size = 32
epochs = 50
learning_rate = 0.000004 

multi_binarizer = MultiLabelBinarizer()

def map_labels_to_integers(ner_labels_list):
    label_to_int = {'O': 0, 'T': 1}
    return [[label_to_int[label] for label in labels] for labels in ner_labels_list]

def read_jsonl(file_path):
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    return data

def process_data(data, tokenizer, max_seq_length=max_seq_length):
    input_ids_list = []
    attention_masks_list = []
    ner_labels_list = []
    senti_labels_list = []

    for item in data:
      text = item["input"]["form"]
      target_begin = item["input"]["target"].get("begin")
      target_end = item["input"]["target"].get("end")
      senti = item["senti"]

      encoded = tokenizer(text, truncation=True, padding='max_length', max_length=max_seq_length)
      input_ids = encoded['input_ids']
      attention_masks = encoded['attention_mask']

      # Create NER labels
      ner_labels = ['O'] * max_seq_length  # Initialize with 'O'

      # If target_begin or target_end is not None, set the labels accordingly
      if target_begin is not None and target_end is not None:
          target_word = text[target_begin:target_end + 1]
          target_tokens = tokenizer(target_word)['input_ids'][1:-1]  # [CLS]와 [SEP] 제거

          # 인코딩된 부분의 위치 찾기
          i = 0
          while i < len(input_ids):
              if input_ids[i:i+len(target_tokens)] == target_tokens:
                  for j in range(i, i+len(target_tokens)):
                      ner_labels[j] = 'T'
                  break  # 타겟 단어는 한 번만 등장한다고 가정
              i += 1

      input_ids_list.append(input_ids)
      attention_masks_list.append(attention_masks)
      ner_labels_list.append(ner_labels)
      senti_labels_list.append(senti)

    # Convert lists to tensors
    input_ids_tensor = torch.tensor(input_ids_list)
    attention_masks_tensor = torch.tensor(attention_masks_list)
    ner_labels_list = map_labels_to_integers(ner_labels_list)
    ner_labels_tensor = torch.tensor(ner_labels_list)

    # Multi-label binarization for sentiment labels
    senti_labels_binarized = multi_binarizer.fit_transform(senti_labels_list)
    senti_labels_tensor = torch.tensor(senti_labels_binarized, dtype=torch.float)

    return input_ids_tensor, attention_masks_tensor, ner_labels_tensor, senti_labels_tensor


# Read JSONL file
file_path = 'train_with_output.jsonl'  # Replace with your JSONL file path
sample_data = read_jsonl(file_path)

# Process the data
input_ids_tensor, attention_masks_tensor, ner_labels_tensor, senti_labels_tensor = process_data(sample_data, tokenizer)

# Create a TensorDataset from your tensors
dataset = TensorDataset(input_ids_tensor, attention_masks_tensor, ner_labels_tensor, senti_labels_tensor)

# Create a DataLoader
train_dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)



# class EmotionModel(nn.Module):
#     def __init__(self, vocab_size, embedding_dim):
#         super(EmotionModel, self).__init__()
#         self.embedding = nn.Embedding(vocab_size, embedding_dim)
#         self.bi_lstm = nn.LSTM(embedding_dim, 128, bidirectional=True, batch_first=True)
#         self.linear_senti = nn.Linear(256, 8)  # 128 * 2 directions = 256
#         self.linear_ner = nn.Linear(256, 2)  # 128 * 2 directions = 256

#     def forward(self, input_ids, attention_masks):
#         x = self.embedding(input_ids)
#         output, (h_n, c_n) = self.bi_lstm(x)
#         h_n = torch.cat((h_n[-2,:,:], h_n[-1,:,:]), dim = 1)  # Concatenate the last hidden state of forward and backward LSTM
#         senti_out = self.linear_senti(h_n)
#         ner_out = self.linear_ner(output)
#         return senti_out, ner_out


# # Define the Model Class
# class EmotionModel(nn.Module):
#     def __init__(self):
#         super(EmotionModel, self).__init__()
#         self.electra = ElectraModel.from_pretrained("monologg/koelectra-base-v3-discriminator")
#         self.bi_lstm = nn.LSTM(768, 128, bidirectional=True, batch_first=True)
#         self.linear_senti = nn.Linear(256, 8)  # 8 classes for sentiment analysis
#         self.linear_ner = nn.Linear(256, 2)  # 2 classes for NER

#     def forward(self, input_ids, attention_masks):
#         outputs = self.electra(input_ids, attention_mask=attention_masks)
#         last_hidden_state = outputs.last_hidden_state
#         output, (h_n, c_n) = self.bi_lstm(last_hidden_state)
#         h_n = torch.cat((h_n[-2,:,:], h_n[-1,:,:]), dim=1)
#         senti_out = self.linear_senti(h_n)
#         ner_out = self.linear_ner(output)
#         return senti_out, ner_out


class EmotionModel(nn.Module):
    def __init__(self):
        super(EmotionModel, self).__init__()
        self.roberta = AutoModel.from_pretrained("beomi/KcELECTRA-base")  # you can choose other versions like "roberta-large"
        self.bi_lstm = nn.LSTM(768, 128, bidirectional=True, batch_first=True)  # make sure to match the dimensions with the chosen Roberta version
        self.linear_senti = nn.Linear(256, 8)  # 8 classes for sentiment analysis
        self.linear_ner = nn.Linear(256, 2)  # 2 classes for NER

    def forward(self, input_ids, attention_masks):
        outputs = self.roberta(input_ids, attention_mask=attention_masks)
        last_hidden_state = outputs.last_hidden_state
        output, (h_n, c_n) = self.bi_lstm(last_hidden_state)
        h_n = torch.cat((h_n[-2,:,:], h_n[-1,:,:]), dim=1)
        senti_out = self.linear_senti(h_n)
        ner_out = self.linear_ner(output)
        return senti_out, ner_out


# Initialize the model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = EmotionModel()
model.to(device)

# Optimizer and Loss Functions
optimizer = Adam(model.parameters(), lr=learning_rate)
senti_loss_fn = BCEWithLogitsLoss().to(device)
ner_loss_fn = nn.CrossEntropyLoss().to(device)

# 초기화
best_dev_f1 = 0.0  # 추가된 부분
save_model_path = "best_model.pth"  # 추가된 부분


# Training Loop
for epoch in range(epochs):
    model.train()
    total_senti_loss = 0
    total_ner_loss = 0
    all_senti_labels = []
    all_senti_preds = []

    for i, batch in enumerate(train_dataloader):
        input_ids, attention_masks, ner_labels, senti_labels = batch
        input_ids = input_ids.to(device)
        attention_masks = attention_masks.to(device)
        ner_labels = ner_labels.to(device)
        senti_labels = senti_labels.to(device)
        optimizer.zero_grad()
        senti_out, ner_out = model(input_ids, attention_masks)

        senti_loss = senti_loss_fn(senti_out, senti_labels)
        ner_out = ner_out.view(-1, ner_out.shape[-1])
        ner_labels = ner_labels.view(-1)
        ner_loss = ner_loss_fn(ner_out, ner_labels)

        total_loss = senti_loss + ner_loss
        total_senti_loss += senti_loss.item()
        total_ner_loss += ner_loss.item()

        total_loss.backward()
        optimizer.step()

        senti_preds = torch.sigmoid(senti_out)
        senti_preds = (senti_preds > 0.5).cpu().numpy().astype(int)
        senti_labels = senti_labels.cpu().numpy().astype(int)

        all_senti_labels.extend(senti_labels.tolist())
        all_senti_preds.extend(senti_preds.tolist())

    senti_f1_score = f1_score(all_senti_labels, all_senti_preds, average='micro')
    print(f'Epoch {epoch+1}, Senti Loss: {total_senti_loss/len(train_dataloader)}, NER Loss: {total_ner_loss/len(train_dataloader)}, Senti F1 Score: {senti_f1_score}')

    model.eval()

    dev_senti_loss = 0
    all_dev_senti_labels = []
    all_dev_senti_preds = []

    with torch.no_grad():
        for i, batch in enumerate(dev_dataloader):
            dev_input_ids, dev_attention_masks, dev_ner_labels, dev_senti_labels = batch
            dev_input_ids = dev_input_ids.to(device)
            dev_attention_masks = dev_attention_masks.to(device)
            dev_ner_labels = dev_ner_labels.to(device)
            dev_senti_labels = dev_senti_labels.to(device)

            dev_senti_out, dev_ner_out = model(dev_input_ids, dev_attention_masks)
            dev_senti_loss += senti_loss_fn(dev_senti_out, dev_senti_labels).item()

            dev_senti_preds = torch.sigmoid(dev_senti_out)
            dev_senti_preds = (dev_senti_preds > 0.5).cpu().numpy().astype(int)
            dev_senti_labels = dev_senti_labels.cpu().numpy().astype(int)
            all_dev_senti_labels.extend(dev_senti_labels.tolist())
            all_dev_senti_preds.extend(dev_senti_preds.tolist())

        dev_senti_loss /= len(dev_dataloader)
        dev_senti_f1_score = f1_score(all_dev_senti_labels, all_dev_senti_preds, average='micro')
        print(f'Epoch {epoch+1}, Dev Senti Loss: {dev_senti_loss}, Dev Senti F1 Score: {dev_senti_f1_score}')
            # 추가된 부분: 검증 데이터에서의 성능이 이전 최고보다 좋을 경우
        if dev_senti_f1_score > best_dev_f1:
            best_dev_f1 = dev_senti_f1_score  # 최고 성능 업데이트
            torch.save(model.state_dict(), save_model_path)  # 모델 저장
            print(f"Saved the new best model with Dev F1: {best_dev_f1}")

# 훈련이 끝나면 최고 성능을 보이는 모델을 불러옴
model.load_state_dict(torch.load(save_model_path))
model.eval()

def test_process_data(data, tokenizer, max_seq_length=max_seq_length):
    input_ids_list = []
    attention_masks_list = []
    ner_labels_list = []
    # senti_labels_list = []
    # multi_binarizer = MultiLabelBinarizer()

    for item in data:
        text = item["input"]["form"]
        target_begin = item["input"]["target"].get("begin")
        target_end = item["input"]["target"].get("end")
        # senti = item["senti"]

        encoded = tokenizer(text, truncation=True, padding='max_length', max_length=max_seq_length)
        input_ids = encoded['input_ids']
        attention_masks = encoded['attention_mask']

        # Create NER labels
        ner_labels = ['O'] * max_seq_length  # Initialize with 'O'

        # If target_begin or target_end is not None, set the labels accordingly
        if target_begin is not None and target_end is not None:
            for i in range(target_begin, target_end + 1):
                ner_labels[i] = 'T'

        input_ids_list.append(input_ids)
        attention_masks_list.append(attention_masks)
        ner_labels_list.append(ner_labels)
        # senti_labels_list.append(senti)

    # Convert lists to tensors
    input_ids_tensor = torch.tensor(input_ids_list)
    attention_masks_tensor = torch.tensor(attention_masks_list)
    ner_labels_list = map_labels_to_integers(ner_labels_list)
    ner_labels_tensor = torch.tensor(ner_labels_list)

    # # Multi-label binarization for sentiment labels
    # senti_labels_binarized = multi_binarizer.fit_transform(senti_labels_list)
    # senti_labels_tensor = torch.tensor(senti_labels_binarized, dtype=torch.float)

    return input_ids_tensor, attention_masks_tensor, ner_labels_tensor # senti_labels_tensor

def evaluate_model(test_data, model, tokenizer, multi_binarizer, device):
    model.eval()  # Set the model to evaluation mode
    output_jsonl = []

    # Process the test data
    test_input_ids_tensor, test_attention_masks_tensor, _ = test_process_data(test_data, tokenizer)

    # Create a DataLoader for the test set
    test_dataset = TensorDataset(test_input_ids_tensor, test_attention_masks_tensor)
    test_dataloader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    with torch.no_grad():
        for i, (input_ids, attention_masks) in enumerate(test_dataloader):
            input_ids = input_ids.to(device)
            attention_masks = attention_masks.to(device)

            # Forward pass
            senti_out, _ = model(input_ids, attention_masks)

            # Get sentiment predictions
            senti_preds = torch.sigmoid(senti_out)
            senti_preds = (senti_preds > 0.5).cpu().numpy().astype(int)  # Convert to boolean labels
            senti_preds_labels = multi_binarizer.inverse_transform(senti_preds)
            for j, preds in enumerate(senti_preds_labels):
                output = {}
                label_order = ["joy", "anticipation", "trust", "surprise", "disgust", "fear", "anger", "sadness"]

                for label in label_order:
                    output[label] = str(label in [l.lower() for l in preds])  # Convert the label to lowercase and check if it exists in the prediction

                # Create the output json object
                json_output = {
                    "id": test_data[i*batch_size + j]["id"],
                    "input": test_data[i*batch_size + j]["input"],
                    "output": output
                }
                output_jsonl.append(json_output)

    return output_jsonl

# You should train your model first before evaluating.
# Assuming `model` is your trained model:

# Read your test data
test_file_path = 'new_test.jsonl'  # Replace with your test JSONL file path
test_data = read_jsonl(test_file_path)

# Evaluate the model
output_jsonl = evaluate_model(test_data, model, tokenizer, multi_binarizer, device)

# Save the output to a JSONL file
with open('Purin.jsonl', 'w', encoding='utf-8') as f:
    for item in output_jsonl:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")